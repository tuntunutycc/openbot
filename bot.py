import io
import logging
import os
from pathlib import PurePosixPath

from dotenv import load_dotenv

load_dotenv(override=True)

import telebot

from services.anthropic_pipeline import AnthropicPipelineError
from services.catalog_pipeline import (
    route_catalog_request,
    run_catalog_batch_n_pipeline,
    run_catalog_batch_pipeline,
)
from services.openclaw_agent import run_openclaw_agent
from services.openclaw_runtime import init_openclaw
from services.photoroom_client import PhotoroomError, remove_background
from services.pipeline_orchestrator import run_ad_pipeline, run_dynamic_image_edit_pipeline


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


def _is_catalog_instruction(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("/catalog") or t.startswith("catalog:")


def _parse_catalog_batch_instruction(text: str) -> tuple[int, str] | None:
    """
    Parse `catalog batch N: prompt` and clamp N to 1..5.
    Returns (count, prompt) or None when not a batch trigger.
    """
    raw = (text or "").strip()
    low = raw.lower()
    if not low.startswith("catalog batch "):
        return None
    rest = raw[len("catalog batch ") :].strip()
    if ":" not in rest:
        return None
    num_part, prompt_part = rest.split(":", 1)
    try:
        count = int(num_part.strip())
    except ValueError:
        return None
    count = max(1, min(count, 5))
    prompt = prompt_part.strip() or "Create a clean premium product catalog layout."
    return count, prompt


def _is_dynamic_edit_instruction(text: str) -> bool:
    """Caption routes to specs/dynamic_image_editing (Claude → v2/edit params), not the ad pipeline."""
    t = (text or "").strip().lower()
    return t.startswith("/edit") or t.startswith("edit:")


def _extract_dynamic_edit_instruction(caption: str) -> str:
    """Strip /edit or edit: prefix; caller ensures caption matches _is_dynamic_edit_instruction."""
    c = (caption or "").strip()
    low = c.lower()
    if low.startswith("/edit"):
        return c[5:].strip()
    if low.startswith("edit:"):
        return c.split(":", 1)[1].strip()
    return ""


def _reply_image_with_optional_text(
    message: telebot.types.Message,
    image_bytes: bytes,
    text: str | None = None,
    output_name: str = "result.png",
) -> None:
    """Send image with optional text, respecting Telegram caption limits."""
    buf = io.BytesIO(image_bytes)
    buf.name = output_name
    buf.seek(0)
    payload_text = (text or "").strip()
    if payload_text and len(payload_text) <= TELEGRAM_CAPTION_MAX:
        try:
            bot.send_photo(
                message.chat.id,
                buf,
                caption=payload_text,
                reply_to_message_id=message.message_id,
            )
        except Exception:
            buf.seek(0)
            bot.send_document(
                message.chat.id,
                buf,
                caption=payload_text,
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
        if payload_text:
            bot.reply_to(message, payload_text)


def _reply_catalog_album(
    message: telebot.types.Message,
    images: list[bytes],
    marketing_copy: str | None,
    *,
    full_fallback: bool,
    partial_fallback: bool,
) -> None:
    """
    Send catalog results as album when possible.
    - Full fallback: single cutout image.
    - Partial fallback: album + note.
    """
    text = (marketing_copy or "").strip()
    if full_fallback or len(images) < 2:
        fallback_note = (
            "Catalog variations fallback mode: quota/billing limits hit, returning a safe mock output."
        )
        joined = f"{fallback_note}\n\n{text}".strip() if text else fallback_note
        _reply_image_with_optional_text(
            message,
            images[0],
            joined,
            output_name="catalog_fallback.png",
        )
        return

    media: list[telebot.types.InputMediaPhoto] = []
    buffers: list[io.BytesIO] = []
    for idx, image in enumerate(images[:3], start=1):
        buf = io.BytesIO(image)
        buf.name = f"catalog_variation_{idx}.png"
        buffers.append(buf)
        media.append(telebot.types.InputMediaPhoto(buf))

    # Caption can only go on the first media item in Telegram albums.
    if text and len(text) <= TELEGRAM_CAPTION_MAX:
        media[0].caption = text

    bot.send_media_group(message.chat.id, media, reply_to_message_id=message.message_id)

    if partial_fallback:
        bot.reply_to(
            message,
            "Some variations used fallback output due to Photoroom quota/billing limits.",
        )
    if text and len(text) > TELEGRAM_CAPTION_MAX:
        bot.reply_to(message, text)


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
            "Use caption prefix '/catalog' or 'catalog:' for catalog layout generation.\n"
            "Use 'catalog batch N: ...' (max N=5) to generate N catalog variations sequentially.\n"
            "Use '/edit …' or 'edit: …' on a photo for dynamic Photoroom edits (Claude maps your text to API parameters).\n"
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
    # Caption routing order: catalog → /edit|edit: (dynamic v2/edit) → default ad pipeline.
    # No caption → Phase 3 background removal only.
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
    parsed_batch = _parse_catalog_batch_instruction(caption)
    if parsed_batch:
        batch_count, batch_instruction = parsed_batch
        try:
            images = run_catalog_batch_n_pipeline(data, name, batch_instruction, batch_count)
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while generating the catalog batch. Please try again.",
            )
            return
        for idx, image in enumerate(images, start=1):
            caption_text = f"Variation {idx}"
            _reply_image_with_optional_text(
                message,
                image,
                caption_text,
                output_name=f"catalog_batch_{idx}.png",
            )
        return

    if caption and _is_catalog_instruction(caption):
        catalog_instruction = caption
        if caption.startswith("/catalog"):
            catalog_instruction = caption.replace("/catalog", "", 1).strip()
        elif caption.lower().startswith("catalog:"):
            catalog_instruction = caption.split(":", 1)[1].strip()
        if not catalog_instruction:
            catalog_instruction = "Create a clean premium product catalog layout."

        routed = route_catalog_request(catalog_instruction)
        if routed["action"] == "catalog_batch":
            batch_count = int(routed["count"])
            batch_instruction = str(routed["base_prompt"])
            batch_prompts = [str(x) for x in routed.get("background_prompts", [])] if isinstance(routed.get("background_prompts"), list) else []
            try:
                images = run_catalog_batch_n_pipeline(
                    data,
                    name,
                    batch_instruction,
                    batch_count,
                    background_prompts=batch_prompts,
                )
            except PhotoroomError as exc:
                bot.reply_to(message, str(exc))
                return
            except Exception:
                bot.reply_to(
                    message,
                    "Something went wrong while generating the catalog batch. Please try again.",
                )
                return
            for idx, image in enumerate(images, start=1):
                prompt_label = ""
                if idx - 1 < len(batch_prompts):
                    prompt_label = batch_prompts[idx - 1]
                caption_text = f"Variation {idx}"
                if prompt_label:
                    caption_text = f"{caption_text}: {prompt_label}"
                _reply_image_with_optional_text(
                    message,
                    image,
                    caption_text,
                    output_name=f"catalog_batch_{idx}.png",
                )
            return

        try:
            batch = run_catalog_batch_pipeline(data, name, catalog_instruction)
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while generating the catalog layout. Please try again.",
            )
            return
        _reply_catalog_album(
            message,
            batch.images,
            batch.marketing_copy,
            full_fallback=batch.full_fallback,
            partial_fallback=batch.partial_fallback,
        )
        return

    # Dynamic image editing: caption must use /edit or edit: so the legacy ad pipeline keeps plain captions.
    if caption and _is_dynamic_edit_instruction(caption):
        instruction = _extract_dynamic_edit_instruction(caption)
        if not instruction:
            bot.reply_to(
                message,
                "Usage: add an instruction after /edit or edit: (e.g. edit: put this on a wooden table).",
            )
            return
        try:
            final_bytes, user_msg = run_dynamic_image_edit_pipeline(data, name, instruction)
        except AnthropicPipelineError as exc:
            bot.reply_to(message, str(exc))
            return
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while running the dynamic edit. Please try again.",
            )
            return
        _reply_image_with_optional_text(
            message,
            final_bytes,
            user_msg,
            output_name="dynamic_edit.png",
        )
        return

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
        _reply_image_with_optional_text(
            message,
            final_bytes,
            marketing,
            output_name="ad_result.png",
        )
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
    parsed_batch = _parse_catalog_batch_instruction(caption)
    if parsed_batch:
        batch_count, batch_instruction = parsed_batch
        try:
            images = run_catalog_batch_n_pipeline(data, filename, batch_instruction, batch_count)
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while generating the catalog batch. Please try again.",
            )
            return
        for idx, image in enumerate(images, start=1):
            caption_text = f"Variation {idx}"
            _reply_image_with_optional_text(
                message,
                image,
                caption_text,
                output_name=f"catalog_batch_{idx}.png",
            )
        return

    if caption and _is_catalog_instruction(caption):
        catalog_instruction = caption
        if caption.startswith("/catalog"):
            catalog_instruction = caption.replace("/catalog", "", 1).strip()
        elif caption.lower().startswith("catalog:"):
            catalog_instruction = caption.split(":", 1)[1].strip()
        if not catalog_instruction:
            catalog_instruction = "Create a clean premium product catalog layout."

        routed = route_catalog_request(catalog_instruction)
        if routed["action"] == "catalog_batch":
            batch_count = int(routed["count"])
            batch_instruction = str(routed["base_prompt"])
            batch_prompts = [str(x) for x in routed.get("background_prompts", [])] if isinstance(routed.get("background_prompts"), list) else []
            try:
                images = run_catalog_batch_n_pipeline(
                    data,
                    filename,
                    batch_instruction,
                    batch_count,
                    background_prompts=batch_prompts,
                )
            except PhotoroomError as exc:
                bot.reply_to(message, str(exc))
                return
            except Exception:
                bot.reply_to(
                    message,
                    "Something went wrong while generating the catalog batch. Please try again.",
                )
                return
            for idx, image in enumerate(images, start=1):
                prompt_label = ""
                if idx - 1 < len(batch_prompts):
                    prompt_label = batch_prompts[idx - 1]
                caption_text = f"Variation {idx}"
                if prompt_label:
                    caption_text = f"{caption_text}: {prompt_label}"
                _reply_image_with_optional_text(
                    message,
                    image,
                    caption_text,
                    output_name=f"catalog_batch_{idx}.png",
                )
            return

        try:
            batch = run_catalog_batch_pipeline(data, filename, catalog_instruction)
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while generating the catalog layout. Please try again.",
            )
            return
        _reply_catalog_album(
            message,
            batch.images,
            batch.marketing_copy,
            full_fallback=batch.full_fallback,
            partial_fallback=batch.partial_fallback,
        )
        return

    if caption and _is_dynamic_edit_instruction(caption):
        instruction = _extract_dynamic_edit_instruction(caption)
        if not instruction:
            bot.reply_to(
                message,
                "Usage: add an instruction after /edit or edit: (e.g. edit: put this on a wooden table).",
            )
            return
        try:
            final_bytes, user_msg = run_dynamic_image_edit_pipeline(data, filename, instruction)
        except AnthropicPipelineError as exc:
            bot.reply_to(message, str(exc))
            return
        except PhotoroomError as exc:
            bot.reply_to(message, str(exc))
            return
        except Exception:
            bot.reply_to(
                message,
                "Something went wrong while running the dynamic edit. Please try again.",
            )
            return
        _reply_image_with_optional_text(
            message,
            final_bytes,
            user_msg,
            output_name="dynamic_edit.png",
        )
        return

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
        _reply_image_with_optional_text(
            message,
            final_bytes,
            marketing,
            output_name="ad_result.png",
        )
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
    log = logging.getLogger(__name__)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_token_here":
        log.error("TELEGRAM_BOT_TOKEN is missing or still set to placeholder in .env.")
        raise SystemExit(1)

    print(f"Token Prefix: {token[:5]}...")
    log.info("Loaded .env with override=True; verifying Telegram session")

    try:
        me = bot.get_me()
        print(f"Bot Active: @{me.username}")
        bot.remove_webhook()
        log.info("Webhook removed; starting infinity polling")
    except Exception as exc:
        log.exception(
            "Startup check failed (token, network, or Telegram API): %s",
            exc,
        )
        raise SystemExit(1) from exc

    try:
        bot.infinity_polling()
    except Exception as exc:
        log.exception("Telegram polling stopped due to connection/API error: %s", exc)
        raise
