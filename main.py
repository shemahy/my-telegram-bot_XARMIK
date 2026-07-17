import logging
import os
import sys
import json
import re
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatType

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID_ENV = os.getenv("ALLOWED_CHAT_ID")          # группа, куда репостятся посты из канала
PHOTO_PATH_OR_URL = os.getenv("PHOTO_PATH_OR_URL")
TIKTOK = os.getenv("TIKTOK_WEBSITE")
YOUTUBE = os.getenv("YOUTUBE_WEBSITE")
TWITCH = os.getenv("TWITCH_WEBSITE")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

# --- Переменные для функции "красивые посты в канал" ---
ADMIN_USER_ID_ENV = os.getenv("ADMIN_USER_ID")               # ID пользователя, которому разрешено создавать посты
POST_CHANNEL_ID_ENV = os.getenv("POST_CHANNEL_ID")           # ID канала, куда публикуются посты с клавиатурой

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

application: Application = None  # инициализируется в main()

# ============================================================
#  ФУНКЦИЯ 1: авто-репост поста канала в группу (без изменений)
# ============================================================

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.edited_message or update.edited_channel_post:
        return

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


# ============================================================
#  ФУНКЦИЯ 2: создание постов с кастомной клавиатурой через
#  Telegram Mini App. Работает только в личке с ботом и только
#  для ADMIN_USER_ID.
# ============================================================

WAITING_CONTENT, WAITING_KEYBOARD, WAITING_CONFIRM = range(3)

URL_RE = re.compile(r"^(https?://|tg://)\S+$", re.IGNORECASE)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MINIAPP_HTML_PATH = os.path.join(BASE_DIR, "miniapp.html")


def _load_miniapp_html() -> str:
    try:
        with open(MINIAPP_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Файл miniapp.html не найден рядом с code.py!")
        return "<h1>miniapp.html не найден на сервере</h1>"


MINIAPP_HTML = _load_miniapp_html()


def _get_admin_id():
    try:
        return int(ADMIN_USER_ID_ENV) if ADMIN_USER_ID_ENV else None
    except (TypeError, ValueError):
        logger.error("ОШИБКА: Неверный формат ADMIN_USER_ID!")
        return None


def _get_post_channel_id():
    try:
        return int(POST_CHANNEL_ID_ENV) if POST_CHANNEL_ID_ENV else None
    except (TypeError, ValueError):
        logger.error("ОШИБКА: Неверный формат POST_CHANNEL_ID!")
        return None


def _get_miniapp_url():
    if not RENDER_EXTERNAL_URL:
        return None
    return f"{RENDER_EXTERNAL_URL}/miniapp"


def parse_keyboard_text(text: str):
    """
    Запасной текстовый формат (на случай если мини-приложение недоступно):

        Текст кнопки - ссылка | Текст кнопки 2 - ссылка 2
        Текст кнопки 3 - ссылка 3

    Каждая строка = отдельный ряд. Кнопки внутри ряда разделяются "|".
    """
    rows = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = []
        for raw_btn in line.split("|"):
            btn = raw_btn.strip()
            if not btn:
                continue
            if " - " not in btn:
                raise ValueError(f"Не могу разобрать кнопку: «{btn}». Нужен формат «Текст - Ссылка».")
            label, url = btn.split(" - ", 1)
            label = label.strip()
            url = url.strip()
            if not label or not url:
                raise ValueError(f"Пустой текст или ссылка в кнопке: «{btn}».")
            if not URL_RE.match(url):
                raise ValueError(f"Некорректная ссылка: «{url}». Ссылка должна начинаться с http:// или https://")
            row.append(InlineKeyboardButton(label, url=url))
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("Не найдено ни одной кнопки.")
    return rows


def parse_keyboard_webapp_json(raw: str):
    """Разбирает JSON, присланный мини-приложением через Telegram.WebApp.sendData()."""
    payload = json.loads(raw)
    rows_data = payload.get("rows", [])
    rows = []
    for row_data in rows_data:
        row = []
        for btn in row_data:
            label = (btn.get("text") or "").strip()
            url = (btn.get("url") or "").strip()
            if not label or not url:
                continue
            if not URL_RE.match(url):
                raise ValueError(f"Некорректная ссылка: «{url}»")
            row.append(InlineKeyboardButton(label, url=url))
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("Клавиатура пустая — добавьте хотя бы одну кнопку.")
    return rows


async def newpost_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    admin_id = _get_admin_id()
    if not admin_id or update.effective_user.id != admin_id:
        # Молча игнорируем всех, кроме назначенного администратора
        return ConversationHandler.END

    if not _get_post_channel_id():
        await update.message.reply_text(
            "❗️ Переменная POST_CHANNEL_ID не настроена на хостинге. "
            "Добавьте её и перезапустите бота."
        )
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "📝 Пришлите содержимое поста — текст или фото с подписью.\n\n"
        "Для отмены в любой момент отправьте /cancel"
    )
    return WAITING_CONTENT


async def newpost_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message

    if message.photo:
        context.user_data["photo_file_id"] = message.photo[-1].file_id
        context.user_data["text"] = message.caption or ""
    elif message.text:
        context.user_data["photo_file_id"] = None
        context.user_data["text"] = message.text
    else:
        await message.reply_text("Пришлите, пожалуйста, текст или фото с подписью.")
        return WAITING_CONTENT

    miniapp_url = _get_miniapp_url()
    if miniapp_url:
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("⚙️ Настроить кнопки поста", web_app=WebAppInfo(url=miniapp_url))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.reply_text(
            "⌨️ Нажмите кнопку ниже, чтобы открыть конструктор — там вы задаёте, сколько "
            "кнопок в каждом ряду, их названия и ссылки.\n\n"
            "Если кнопки не нужны — отправьте /skip",
            reply_markup=keyboard,
        )
    else:
        await message.reply_text(
            "⌨️ Пришлите кнопки в формате:\n\n"
            "<code>Текст кнопки - ссылка | Текст кнопки 2 - ссылка 2\n"
            "Текст кнопки 3 - ссылка 3</code>\n\n"
            "Каждая новая строка — новый ряд. Кнопки в одном ряду разделяйте «|».\n"
            "Если кнопки не нужны — отправьте /skip",
            parse_mode="HTML",
        )
    return WAITING_KEYBOARD


async def newpost_receive_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    raw = message.web_app_data.data
    try:
        rows = parse_keyboard_webapp_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        await message.reply_text(
            f"⚠️ Не удалось обработать клавиатуру: {e}\nОткройте конструктор ещё раз.",
            reply_markup=ReplyKeyboardRemove(),
        )
        miniapp_url = _get_miniapp_url()
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("⚙️ Настроить кнопки поста", web_app=WebAppInfo(url=miniapp_url))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.reply_text("Попробуйте ещё раз:", reply_markup=keyboard)
        return WAITING_KEYBOARD

    context.user_data["keyboard_rows"] = rows
    await message.reply_text("Клавиатура получена ✅", reply_markup=ReplyKeyboardRemove())
    return await newpost_show_preview(update, context)


async def newpost_receive_keyboard_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запасной путь: админ прислал клавиатуру текстом вместо мини-приложения."""
    message = update.effective_message
    try:
        rows = parse_keyboard_text(message.text or "")
    except ValueError as e:
        await message.reply_text(
            f"⚠️ {e}\n\nПопробуйте ещё раз, откройте конструктор кнопкой выше, либо отправьте /skip."
        )
        return WAITING_KEYBOARD

    context.user_data["keyboard_rows"] = rows
    await message.reply_text("Клавиатура получена ✅", reply_markup=ReplyKeyboardRemove())
    return await newpost_show_preview(update, context)


async def newpost_skip_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyboard_rows"] = None
    await update.message.reply_text("Ок, без кнопок.", reply_markup=ReplyKeyboardRemove())
    return await newpost_show_preview(update, context)


async def newpost_show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    rows = context.user_data.get("keyboard_rows")
    preview_rows = [row[:] for row in rows] if rows else []
    preview_rows.append([
        InlineKeyboardButton("✅ Опубликовать", callback_data="newpost_confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="newpost_cancel"),
    ])
    reply_markup = InlineKeyboardMarkup(preview_rows)

    photo_file_id = context.user_data.get("photo_file_id")
    text = context.user_data.get("text", "")

    await message.reply_text("Вот как будет выглядеть пост 👇 (кнопки «Опубликовать/Отмена» в канал не попадут)")
    if photo_file_id:
        await message.reply_photo(photo=photo_file_id, caption=text, reply_markup=reply_markup)
    else:
        await message.reply_text(text=text, reply_markup=reply_markup)

    return WAITING_CONFIRM


async def newpost_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    channel_id = _get_post_channel_id()
    photo_file_id = context.user_data.get("photo_file_id")
    text = context.user_data.get("text", "")
    rows = context.user_data.get("keyboard_rows")
    reply_markup = InlineKeyboardMarkup(rows) if rows else None

    try:
        if photo_file_id:
            await context.bot.send_photo(
                chat_id=channel_id, photo=photo_file_id, caption=text, reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(chat_id=channel_id, text=text, reply_markup=reply_markup)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ Пост опубликован в канал!")
        logger.info(f"Пост опубликован в канал {channel_id} пользователем {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")
        await query.message.reply_text(f"❌ Не удалось опубликовать пост: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def newpost_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("❌ Создание поста отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def newpost_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Создание поста отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


newpost_conversation = ConversationHandler(
    entry_points=[CommandHandler("newpost", newpost_start, filters=filters.ChatType.PRIVATE)],
    states={
        WAITING_CONTENT: [
            MessageHandler(
                filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
                newpost_receive_content,
            )
        ],
        WAITING_KEYBOARD: [
            CommandHandler("skip", newpost_skip_keyboard),
            MessageHandler(filters.StatusUpdate.WEB_APP_DATA, newpost_receive_webapp_data),
            MessageHandler(
                filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
                newpost_receive_keyboard_text,
            ),
        ],
        WAITING_CONFIRM: [
            CallbackQueryHandler(newpost_confirm, pattern="^newpost_confirm$"),
            CallbackQueryHandler(newpost_cancel_callback, pattern="^newpost_cancel$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", newpost_cancel_command)],
)


# ============================================================
#  Веб-сервер: принимает вебхук Telegram И отдаёт мини-приложение
# ============================================================

async def handle_telegram_webhook(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad Request")
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return web.Response(text="OK")


async def handle_miniapp(request: web.Request) -> web.Response:
    return web.Response(text=MINIAPP_HTML, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="Bot is running")


async def on_startup(aio_app: web.Application) -> None:
    await application.initialize()
    await application.start()
    webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
    await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Вебхук установлен: {webhook_url}")
    logger.info(f"Мини-приложение доступно на: {_get_miniapp_url()}")


async def on_cleanup(aio_app: web.Application) -> None:
    await application.stop()
    await application.shutdown()


def main() -> None:
    global application

    if not BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная TELEGRAM_BOT_TOKEN не настроена!")
        sys.exit(1)

    if not RENDER_EXTERNAL_URL:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная RENDER_EXTERNAL_URL не настроена на Render!")
        sys.exit(1)

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_channel_post_in_group))
    application.add_handler(newpost_conversation)

    aio_app = web.Application()
    aio_app.router.add_get("/", handle_health)
    aio_app.router.add_get("/miniapp", handle_miniapp)
    aio_app.router.add_post(f"/{BOT_TOKEN}", handle_telegram_webhook)
    aio_app.on_startup.append(on_startup)
    aio_app.on_cleanup.append(on_cleanup)

    port = int(os.getenv("PORT", 10000))
    logger.info("Запуск бота в режиме WEBHOOK (aiohttp)...")
    web.run_app(aio_app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
