import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")
PHOTO_PATH_OR_URL = os.getenv("PHOTO_PATH_OR_URL")
TIKTOK = os.getenv("TIKTOK_WEBSITE")
YOUTUBE = os.getenv("YOUTUBE_WEBSITE")
TWITCH = os.getenv("TWITCH_WEBSITE")

STATIC_MESSAGE = "Вот, кстати, его соц-сети! 🤵👇\n\nПодписывайтесь!!! 🤠"

# Динамическое создание конфигурации кнопок
BUTTONS_CONFIG = []
if TIKTOK: BUTTONS_CONFIG.append(("🎵 TikTok", TIKTOK))
if YOUTUBE: BUTTONS_CONFIG.append(("🎥 YouTube", YOUTUBE))
if TWITCH: BUTTONS_CONFIG.append(("📷 Twitch", TWITCH))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Веб-сервер для прохождения Health Check на Render
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

    # Проверка ALLOWED_CHAT_ID (если она задана)
    if ALLOWED_CHAT_ID_ENV:
        try:
            allowed_chat_id = int(ALLOWED_CHAT_ID_ENV)
            if message.chat.id != allowed_chat_id:
                logger.debug(f"Сообщение проигнорировано: ID чата {message.chat.id} не совпадает.")
                return
        except (TypeError, ValueError):
            logger.error("ОШИБКА: Неверный формат ALLOWED_CHAT_ID!")
            return

    # Проверяем, что сообщение пришло от имени канала в группу обсуждения
    if message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        # Создаем клавиатуру с кнопками соцсетей
        keyboard = []
        row = []
        for text, url in BUTTONS_CONFIG:
            if url: 
                row.append(InlineKeyboardButton(text, url=url))
                if len(row) == 2:  # По 2 кнопки в ряд
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        try:
            # Если указана ссылка на фото, отправляем фото с текстом
            if PHOTO_PATH_OR_URL:
                await message.reply_photo(
                    photo=PHOTO_PATH_OR_URL,
                    caption=STATIC_MESSAGE,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено фото-сообщение в ответ на пост {message.message_id}")
            else:
                # Иначе отправляем обычный текст
                await message.reply_text(
                    text=STATIC_MESSAGE,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено текстовое сообщение в ответ на пост {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}")

def main() -> None:
    if not BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная TELEGRAM_BOT_TOKEN не настроена!")
        sys.exit(1)

    # Запуск веб-сервера для Render в отдельном потоке
    threading.Thread(target=start_web_server, daemon=True).start()

    # Запуск Telegram-бота (библиотека сама создаст нужный event loop)
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    logger.info("Бот успешно инициализирован и запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
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
