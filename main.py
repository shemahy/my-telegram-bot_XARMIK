import logging
import os
import sys
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
# Сюда мы передадим ID твоей группы через настройки Render
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")

STATIC_MESSAGE = "вот кстати мои соцсети"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    # Проверяем, задан ли ID разрешенной группы в настройках Render
    try:
        allowed_chat_id = int(ALLOWED_CHAT_ID_ENV)
    except (TypeError, ValueError):
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная ALLOWED_CHAT_ID не задана или указана неверно (должно быть числом)!")
        return

    # Проверка безопасности: если ID группы не совпадает с разрешенным, бот ничего не делает
    if message.chat.id != allowed_chat_id:
        logger.warning(
            f"ВНИМАНИЕ! Попытка вызова бота в неразрешенной группе! "
            f"ID группы: {message.chat.id}. Разрешенный ID: {allowed_chat_id}. Игнорируем сообщение."
        )
        return

    # Если проверка пройдена, проверяем, пришло ли сообщение от канала
    if message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        channel_title = message.sender_chat.title or "Неизвестный канал"
        group_title = message.chat.title or "Неизвестная группа"
        
        logger.info(f"Новый пост от канала '{channel_title}' в разрешенной группе '{group_title}' (ID: {message.chat.id})")
        try:
            await message.reply_text(STATIC_MESSAGE)
            logger.info(f"Успешно ответили на пост ID {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}", exc_info=True)

def main() -> None:
    if not BOT_TOKEN: 
        logger.error("Ошибка: Токен TELEGRAM_BOT_TOKEN не найден в переменных окружения на Render!")
        sys.exit(1)
        
    if not ALLOWED_CHAT_ID_ENV:
        logger.error("Ошибка: ID разрешенной группы (ALLOWED_CHAT_ID) не найден в переменных окружения!")
        sys.exit(1)

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    logger.info("Бот запущен с защитой по ID группы и ожидает обновлений...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
