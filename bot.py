import io
import logging
import os
from pathlib import PurePosixPath

import telebot
from dotenv import load_dotenv

from services.anthropic_pipeline import AnthropicPipelineError
from services.openclaw_agent import run_openclaw_agent
from services.openclaw_runtime import init_openclaw
from services.photoroom_client import PhotoroomError, remove_background
from services.pipeline_orchestrator import run_ad_pipeline


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_token_here":
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing or still set to placeholder in .env."
    )

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
OPENCLAW_HANDLE = init_openclaw()

MAX_IMAGE_BYTES = 20 * 1024 * 1024
TELEGRAM_CAPTION_MAX = 1024


def _is_image_document(message: telebot.types.Message) -> bool:
    doc = message.document
    if not doc or not doc.mime_type:
        return False
    return doc.mime_type.lower().startswith("image/")


def _download_telegram_file(file_id: str) -> tuple[bytes, str]:
    info = bot.get_file(file_id)
    if not info or not info.file_path:
        raise ValueError("Telegram file path missing")
    raw = bot.download_file(info.file_path)
    if not isinstance(raw, bytes):
        raw = bytes(raw)
    name = PurePosixPath(info.file_path).name or "image.jpg"
    return raw, name


def _reply_pipeline_result(
    message: telebot.types.Message, image_bytes: bytes, marketing_copy: str
) -> None:
    """Send final (or fallback) image plus marketing copy per Telegram limits."""
    buf = io.BytesIO(image_bytes)
    buf.name = "ad_result.png"
    buf.seek(0)
    if len(marketing_copy) <= TELEGRAM_CAPTION_MAX:
        try:
            bot.send_photo(
                message.chat.id,
                buf,
                caption=marketing_copy,
                reply_to_message_id=message.message_id,
            )
        except Exception:
            buf.seek(0)
            bot.send_document(
                message.chat.id,
                buf,
                caption=marketing_copy,
                reply_to_message_id=message.message_id,
            )
    else:
        try:
            bot.send_photo(
                message.chat.id,
                buf,
                reply_to_message_id=message.message_id,
            )
        except Exception:
            buf.seek(0)
            bot.send_document(
                message.chat.id,
                buf,
                reply_to_message_id=message.message_id,
            )
        bot.reply_to(message, marketing_copy)


def _process_and_reply_image(
    message: telebot.types.Message, image_bytes: bytes, filename: str
) -> None:
    if len(image_bytes) > MAX_IMAGE_BYTES:
        bot.reply_to(
            message,
            f"Image is too large. Please send a file under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )
        return
    try:
        out = remove_background(image_bytes, filename=filename)
    except PhotoroomError as exc:
        bot.reply_to(message, str(exc))
        return
    buf = io.BytesIO(out)
    buf.name = "photoroom.png"
    buf.seek(0)
    try:
        bot.send_photo(
            message.chat.id,
            buf,
            reply_to_message_id=message.message_id,
        )
    except Exception:
        buf.seek(0)
        bot.send_document(
            message.chat.id,
            buf,
            reply_to_message_id=message.message_id,
        )


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message) -> None:
    openclaw_status = "ready" if OPENCLAW_HANDLE.is_ready else "fallback mode"
    bot.reply_to(
        message,
        (
            "Bot is online. Send any text message and I will echo it back.\n"
            "Send a product photo (or image file) without a caption to remove background only.\n"
            "Send a photo with a caption (e.g. beach ad background) to run the full AI ad pipeline.\n"
            "Use /agent <message> or prefix with 'agent:' to route through OpenClaw.\n"
            f"OpenClaw status: {openclaw_status}"
        ),
    )


@bot.message_handler(commands=["agent"])
def handle_agent_command(message: telebot.types.Message) -> None:
    user_text = message.text.replace("/agent", "", 1).strip() if message.text else ""
    if not user_text:
        bot.reply_to(message, "Usage: /agent <your request>")
        return

    context = {"chat_id": message.chat.id, "user_id": message.from_user.id}
    reply = run_openclaw_agent(user_text=user_text, context=context, handle=OPENCLAW_HANDLE)
    bot.reply_to(message, reply)


@bot.message_handler(content_types=["photo"])
def handle_photo(message: telebot.types.Message) -> None:
    # Caption present → full pipeline (segment + Claude + v2/edit). No caption → Phase 3 cut-out only.
    photos = message.photo
    if not photos:
        bot.reply_to(message, "No photo found in this message.")
        return
    best = photos[-1]
    try:
        data, name = _download_telegram_file(best.file_id)
    except ValueError:
        bot.reply_to(message, "Could not download this photo from Telegram.")
        return
    except Exception:
        bot.reply_to(message, "Could not download this photo from Telegram.")
        return
    if len(data) > MAX_IMAGE_BYTES:
        bot.reply_to(
            message,
            f"Image is too large. Please send a file under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )
        return

    caption = (message.caption or "").strip()
    if caption:
        try:
            final_bytes, marketing = run_ad_pipeline(data, name, caption)
        except AnthropicPipelineError as exc:
            bot.reply_to(message, str(exc))
            return
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while running the ad pipeline. Please try again.",
            )
            return
        _reply_pipeline_result(message, final_bytes, marketing)
        return

    _process_and_reply_image(message, data, name)


@bot.message_handler(content_types=["document"], func=_is_image_document)
def handle_image_document(message: telebot.types.Message) -> None:
    doc = message.document
    if not doc:
        return
    try:
        data, path_name = _download_telegram_file(doc.file_id)
    except ValueError:
        bot.reply_to(message, "Could not download this file from Telegram.")
        return
    except Exception:
        bot.reply_to(message, "Could not download this file from Telegram.")
        return
    filename = doc.file_name or path_name
    if len(data) > MAX_IMAGE_BYTES:
        bot.reply_to(
            message,
            f"Image is too large. Please send a file under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )
        return

    caption = (message.caption or "").strip()
    if caption:
        try:
            final_bytes, marketing = run_ad_pipeline(data, filename, caption)
        except AnthropicPipelineError as exc:
            bot.reply_to(message, str(exc))
            return
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while running the ad pipeline. Please try again.",
            )
            return
        _reply_pipeline_result(message, final_bytes, marketing)
        return

    _process_and_reply_image(message, data, filename)


@bot.message_handler(func=lambda message: bool(message.text))
def handle_echo(message: telebot.types.Message) -> None:
    if message.text.startswith("agent:"):
        user_text = message.text.split("agent:", 1)[1].strip()
        if not user_text:
            bot.reply_to(message, "Please provide text after 'agent:'.")
            return

        context = {"chat_id": message.chat.id, "user_id": message.from_user.id}
        reply = run_openclaw_agent(
            user_text=user_text,
            context=context,
            handle=OPENCLAW_HANDLE,
        )
        bot.reply_to(message, reply)
        return

    bot.reply_to(message, message.text)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    bot.infinity_polling()
