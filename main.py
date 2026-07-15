import logging
import os
import sys
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")
PHOTO_PATH_OR_URL = os.getenv("PHOTO_PATH_OR_URL")
TIKTOK = os.getenv("TIKTOK_WEBSITE")
YOUTUBE = os.getenv("YOUTUBE_WEBSITE")
TWITCH = os.getenv("TWITCH_WEBSITE")

STATIC_MESSAGE = "Вот, кстати, его соц-сети! 🤵👇\n\nПодписывайтесь!!! 🤠"

BUTTONS_CONFIG = []
if TIKTOK: BUTTONS_CONFIG.append(("🎵 TikTok", TIKTOK))
if YOUTUBE: BUTTONS_CONFIG.append(("🎥 YouTube", YOUTUBE))
if TWITCH: BUTTONS_CONFIG.append(("📷 Twitch", TWITCH))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот работает!".encode("utf-8"))

    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Вспомогательный веб-сервер запущен на порту {port}")
    server.serve_forever()

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    try:
        allowed_chat_id = int(ALLOWED_CHAT_ID_ENV)
    except (TypeError, ValueError):
        logger.error("ОШИБКА: ALLOWED_CHAT_ID не задана!")
        return

    if message.chat.id != allowed_chat_id:
        return

    if message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        keyboard = []
        row = []
        for text, url in BUTTONS_CONFIG:
            if url: 
                row.append(InlineKeyboardButton(text, url=url))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if PHOTO_PATH_OR_URL:
                await message.reply_photo(
                    photo=PHOTO_PATH_OR_URL,
                    caption=STATIC_MESSAGE,
                    reply_markup=reply_markup
                )
            else:
                await message.reply_text(
                    text=STATIC_MESSAGE,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

def main() -> None:
    if not BOT_TOKEN or not ALLOWED_CHAT_ID_ENV:
        logger.error("Ошибка: Переменные окружения не настроены!")
        sys.exit(1)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    threading.Thread(target=start_web_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()    logger.info("Бот запущен...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
