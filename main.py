import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")

STATIC_MESSAGE = "вот кстати мои соцсети"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- ВЕБ-СЕРВЕР ДЛЯ ОБХОДА ОГРАНИЧЕНИЙ RENDER (FREE TIER) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот работает!".encode("utf-8"))

    def log_message(self, format, *args):
        # Отключаем лишний спам в логах от пингов Render
        pass

def start_web_server():
    # Render автоматически передает порт в переменную окружения PORT
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Вспомогательный веб-сервер запущен на порту {port}")
    server.serve_forever()

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    # Проверяем, задан ли ID разрешенной группы
    try:
        allowed_chat_id = int(ALLOWED_CHAT_ID_ENV)
    except (TypeError, ValueError):
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная ALLOWED_CHAT_ID не задана или указана неверно!")
        return

    # Проверка безопасности
    if message.chat.id != allowed_chat_id:
        logger.warning(
            f"ВНИМАНИЕ! Попытка вызова бота в неразрешенной группе! ID: {message.chat.id}"
        )
        return

    # Если проверка пройдена, проверяем, пришло ли сообщение от канала
    if message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        channel_title = message.sender_chat.title or "Неизвестный канал"
        group_title = message.chat.title or "Неизвестная группа"
        
        logger.info(f"Новый пост от '{channel_title}' в разрешенной группе '{group_title}'")
        try:
            await message.reply_text(STATIC_MESSAGE)
            logger.info(f"Успешно ответили на пост ID {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}", exc_info=True)

def main() -> None:
    if not BOT_TOKEN: 
        logger.error("Ошибка: Токен TELEGRAM_BOT_TOKEN не найден!")
        sys.exit(1)
        
    if not ALLOWED_CHAT_ID_ENV:
        logger.error("Ошибка: ID разрешенной группы не найден!")
        sys.exit(1)

    # Запускаем вспомогательный веб-сервер в отдельном потоке, чтобы Render не отключал бота
    threading.Thread(target=start_web_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    logger.info("Бот запущен с защитой по ID и ожидает обновлений...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
