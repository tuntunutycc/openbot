import os

import telebot
from dotenv import load_dotenv

from services.openclaw_agent import run_openclaw_agent
from services.openclaw_runtime import init_openclaw


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_token_here":
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing or still set to placeholder in .env."
    )

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
OPENCLAW_HANDLE = init_openclaw()


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message) -> None:
    openclaw_status = "ready" if OPENCLAW_HANDLE.is_ready else "fallback mode"
    bot.reply_to(
        message,
        (
            "Bot is online. Send any text message and I will echo it back.\n"
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
    bot.infinity_polling()
