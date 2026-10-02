import os
import csv
import logging
import sqlite3
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAX_TEXT_LEN = 500

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_NAME = "requests.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_request(user_id, username, text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO requests (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_requests(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, text, created_at FROM requests WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_requests():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, username, text, created_at FROM requests ORDER BY id DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def export_to_csv():
    rows = get_all_requests()
    filename = f"requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "User ID", "Username", "Текст", "Дата"])
        writer.writerows(rows)
    return filename


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📝 Оставить заявку", "📋 Мои заявки"]],
    resize_keyboard=True,
)

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📝 Оставить заявку", "📋 Мои заявки"],
     ["📊 Все заявки", "📥 Скачать CSV"]],
    resize_keyboard=True,
)


def get_keyboard(user_id):
    return ADMIN_KEYBOARD if user_id == ADMIN_ID else MAIN_KEYBOARD


ASKING_TEXT = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот для приёма заявок. 🤖\n"
        "Выберите действие на клавиатуре:",
        reply_markup=get_keyboard(user.id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "Я умею:\n"
        "/start - начать работу\n"
        "/help - эта справка\n"
        "/cancel - отменить ввод\n\n"
        "Нажмите «📝 Оставить заявку», чтобы отправить заявку.",
        reply_markup=get_keyboard(user.id),
    )


async def ask_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Напишите текст вашей заявки (до {MAX_TEXT_LEN} символов). Например:\n"
        "«Нужен сайт-визитка для кофейни»\n\n"
        "Для отмены нажмите /cancel"
    )
    return ASKING_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if len(text) > MAX_TEXT_LEN:
        await update.message.reply_text(
            f"❌ Слишком длинный текст! Максимум {MAX_TEXT_LEN} символов.\n"
            f"Сейчас: {len(text)}. Попробуйте ещё раз.",
            reply_markup=get_keyboard(user.id),
        )
        return ASKING_TEXT

    save_request(user.id, user.username, text)
    logger.info("Заявка сохранена от user_id=%s", user.id)

    await update.message.reply_text(
        "✅ Заявка принята! Мы свяжемся с вами.",
        reply_markup=get_keyboard(user.id),
    )

    if ADMIN_ID and user.id != ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 Новая заявка\n"
                     f"От: @{user.username or 'нет username'} (id={user.id})\n"
                     f"Текст: {text}",
            )
        except Exception as e:
            logger.error("Не удалось уведомить админа: %s", e)

    return ConversationHandler.END


async def list_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rows = get_requests(user.id)

    if not rows:
        await update.message.reply_text(
            "У вас пока нет заявок. Нажмите «📝 Оставить заявку».",
            reply_markup=get_keyboard(user.id),
        )
        return

    lines = []
    for rid, text, created in rows:
        lines.append(f"#{rid} ({created[:10]})\n{text}")
    await update.message.reply_text(
        "📋 Ваши заявки:\n\n" + "\n\n".join(lines),
        reply_markup=get_keyboard(user.id),
    )


async def admin_all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
        return

    rows = get_all_requests()
    if not rows:
        await update.message.reply_text("Заявок пока нет.", reply_markup=ADMIN_KEYBOARD)
        return

    lines = []
    for rid, uid, uname, text, created in rows:
        lines.append(f"#{rid} | @{uname or 'нет'} (id={uid}) | {created[:10]}\n{text}")
    await update.message.reply_text(
        "📊 Все заявки:\n\n" + "\n\n".join(lines[:20]),
        reply_markup=ADMIN_KEYBOARD,
    )


async def admin_export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет доступа к этой функции.")
        return

    filename = export_to_csv()
    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=filename,
            caption="📥 Все заявки в CSV",
        )
    os.remove(filename)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "Отменено. Выберите действие.",
        reply_markup=get_keyboard(user.id),
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка: %s", context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Попробуйте ещё раз."
        )


def main():
    if not TOKEN:
        raise ValueError(
            "Не задан токен! Установите переменную окружения BOT_TOKEN.\n"
            "Пример: export BOT_TOKEN='ваш_токен'"
        )
    if not ADMIN_ID:
        logger.warning(
            "ADMIN_ID не задан. Админ-функции будут недоступны. "
            "Установите переменную окружения ADMIN_ID."
        )

    init_db()
    logger.info("База данных инициализирована")

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text("📝 Оставить заявку"), ask_text),
        ],
        states={
            ASKING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Text("📋 Мои заявки"), list_requests))
    app.add_handler(MessageHandler(filters.Text("📊 Все заявки"), admin_all_requests))
    app.add_handler(MessageHandler(filters.Text("📥 Скачать CSV"), admin_export_csv))
    app.add_error_handler(error_handler)

    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
    
