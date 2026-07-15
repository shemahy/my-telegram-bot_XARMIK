import logging
import os
import sys
import asyncio 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")
PHOTO_PATH_OR_URL = os.getenv("PHOTO_PATH_OR_URL")
TIKTOK = os.getenv("TIKTOK_WEBSITE")
YOUTUBE = os.getenv("YOUTUBE_WEBSITE")
TWITCH = os.getenv("TWITCH_WEBSITE")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
STATIC_MESSAGE = "<b>Вот, кстати, его соц-сети! 🤵👇</b>\n\n<code>Подписывайтесь!!! 🤠</code>"

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

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if ALLOWED_CHAT_ID_ENV:
        try:
            allowed_chat_id = int(ALLOWED_CHAT_ID_ENV)
            if message.chat.id != allowed_chat_id:
                logger.debug(f"Сообщение проигнорировано: ID чата {message.chat.id} не совпадает.")
                return
        except (TypeError, ValueError):
            logger.error("ОШИБКА: Неверный формат ALLOWED_CHAT_ID!")
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
            
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        try:
            if PHOTO_PATH_OR_URL:
                await message.reply_photo(
                    photo=PHOTO_PATH_OR_URL,
                    caption=STATIC_MESSAGE,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                logger.info(f"Отправлено фото-сообщение в ответ на пост {message.message_id}")
            else:
                await message.reply_text(
                    text=STATIC_MESSAGE,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                logger.info(f"Отправлено текстовое сообщение в ответ на пост {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}")

def main() -> None:
    if not BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная TELEGRAM_BOT_TOKEN не настроена!")
        sys.exit(1)

    if not RENDER_EXTERNAL_URL:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная RENDER_EXTERNAL_URL не настроена на Render!")
        sys.exit(1)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    
    port = int(os.getenv("PORT", 10000))
    
    logger.info("Запуск бота в режиме WEBHOOK...")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
