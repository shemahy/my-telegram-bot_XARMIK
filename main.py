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
STATIC_MESSAGE = "Вот, кстати, его соц-сети!🤵👇\n\nПодпысывайтесь!!!🤠"

BUTTONS_CONFIG = [
    ("🎵 TikTok", TIKTOK),
    ("🎥 YouTube", YOUTUBE),
    ("📷 Twitch", TWITCH),
]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(name)

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
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная ALLOWED_CHAT_ID не задана или указана неверно!")
        return

    if message.chat.id != allowed_chat_id:
        logger.warning(
            f"ВНИМАНИЕ! Попытка вызова бота в неразрешенной группе! ID: {message.chat.id}"
        )
        return

    if message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        channel_title = message.sender_chat.title or "Неизвестный канал"
        group_title = message.chat.title or "Неизвестная группа"
        
        logger.info(f"Новый пост от '{channel_title}' в разрешенной группе '{group_title}'")
        
        keyboard = []
        current_row = []
        
        for text, url in BUTTONS_CONFIG:
            button = InlineKeyboardButton(text, url=url)
            current_row.append(button)
            
            if len(current_row) == 2:
                keyboard.append(current_row)
                current_row = []
                
        if current_row:
            keyboard.append(current_row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Изменено на отправку фото с подписью
            await message.reply_photo(photo=PHOTO_PATH_OR_URL, caption=STATIC_MESSAGE, reply_markup=reply_markup, parse_mode="MarkdownV2")
            logger.info(f"Успешно ответили на пост ID {message.message_id} с авто-кнопками")
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}", exc_info=True)

def main() -> None:
    if not BOT_TOKEN: 
        logger.error("Ошибка: Токен TELEGRAM_BOT_TOKEN не найден!")
        sys.exit(1)
        
    if not ALLOWED_CHAT_ID_ENV:
        logger.error("Ошибка: ID разрешенной группы не найден!")
        sys.exit(1)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    threading.Thread(target=start_web_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    logger.info("Бот запущен, авто-распределение кнопок готово...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}", exc_info=True)
        sys.exit(1)

if name == "main":
    main()
