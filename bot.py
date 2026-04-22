import os

import telebot
from dotenv import load_dotenv


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_token_here":
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing or still set to placeholder in .env."
    )

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message) -> None:
    bot.reply_to(
        message,
        "Bot is online. Send any text message and I will echo it back.",
    )


@bot.message_handler(func=lambda message: bool(message.text))
def handle_echo(message: telebot.types.Message) -> None:
    bot.reply_to(message, message.text)


if __name__ == "__main__":
    bot.infinity_polling()
