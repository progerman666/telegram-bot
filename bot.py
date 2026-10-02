import os

# Создаём папку output
os.makedirs("./output", exist_ok=True)

# ============ bot.py ============
bot_py = '''"""
Telegram-бот для приёма заявок с сохранением в базу данных.
Портфолио-кейс: Python + python-telegram-bot + SQLite + логирование.

Как запустить:
1. pip install -r requirements.txt
2. Получи токен у @BotFather в Telegram
3. Запусти: python bot.py
"""

import os
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

# ---------- Настройка ----------
# Токен берём из переменной окружения (безопаснее, чем в коде)
TOKEN = os.getenv("BOT_TOKEN", "")

# ---------- Логирование ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- База данных ----------
DB_NAME = "requests.db"


def init_db():
    """Создаёт таблицу заявок, если её нет."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_request(user_id, username, text):
    """Сохраняет заявку в базу."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO requests (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_requests(user_id):
    """Возвращает все заявки пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, text, created_at FROM requests WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Клавиатура ----------
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📝 Оставить заявку", "📋 Мои заявки"]],
    resize_keyboard=True,
)

# ---------- Состояния диалога ----------
ASKING_TEXT = 1


# ---------- Обработчики ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    await update.message.reply_text(
        "Привет! Я бот для приёма заявок. 🤖\\n"
        "Выберите действие на клавиатуре:",
        reply_markup=MAIN_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    await update.message.reply_text(
        "Я умею:\\n"
        "/start - начать работу\\n"
        "/help - эта справка\\n"
        "/cancel - отменить ввод\\n\\n"
        "Нажмите «📝 Оставить заявку», чтобы отправить заявку.",
        reply_markup=MAIN_KEYBOARD,
    )


async def ask_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог: просит ввести текст заявки."""
    await update.message.reply_text(
        "Напишите текст вашей заявки. Например:\\n"
        "«Нужен сайт-визитка для кофейни»\\n\\n"
        "Для отмены нажмите /cancel"
    )
    return ASKING_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает текст заявки и сохраняет в базу."""
    user = update.effective_user
    text = update.message.text

    save_request(user.id, user.username, text)
    logger.info("Заявка сохранена от user_id=%s", user.id)

    await update.message.reply_text(
        "✅ Заявка принята! Мы свяжемся с вами.",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END


async def list_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все заявки пользователя."""
    user = update.effective_user
    rows = get_requests(user.id)

    if not rows:
        await update.message.reply_text(
            "У вас пока нет заявок. Нажмите «📝 Оставить заявку».",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    lines = []
    for rid, text, created in rows:
        lines.append(f"#{rid} ({created[:10]})\\n{text}")
    await update.message.reply_text(
        "📋 Ваши заявки:\\n\\n" + "\\n\\n".join(lines),
        reply_markup=MAIN_KEYBOARD,
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог."""
    await update.message.reply_text(
        "Отменено. Выберите действие.",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ошибки, чтобы бот не падал."""
    logger.error("Ошибка: %s", context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Попробуйте ещё раз."
        )


# ---------- Запуск ----------
def main():
    if not TOKEN:
        raise ValueError(
            "Не задан токен! Установите переменную окружения BOT_TOKEN "
            "или впишите токен в код."
        )

    init_db()
    logger.info("База данных инициализирована")

    app = Application.builder().token(TOKEN).build()

    # Диалог приёма заявки
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
    app.add_error_handler(error_handler)

    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
'''

# ============ requirements.txt ============
requirements = """python-telegram-bot==21.6
"""

# ============ README.md ============
readme = """# Telegram-бот для приёма заявок 🤖

Бот принимает заявки от пользователей и сохраняет их в базу данных SQLite.
Готовый кейс для портфолио: Python + python-telegram-bot + SQLite + логирование.

## Возможности
- 📝 Приём заявок через диалог с пользователем
- 📋 Просмотр своих заявок
- 💾 Сохранение данных в базу SQLite
- 🛡 Обработка ошибок и логирование
- ⌨️ Удобное меню с кнопками

## Стек
- Python 3.10+
- python-telegram-bot 21.x
- SQLite (встроенная база данных)
- logging (логирование)

## Как запустить

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Получите токен у [@BotFather](https://t.me/BotFather) в Telegram.

3. Задайте токен переменной окружения:
   ```bash
   # Windows (PowerShell)
   $env:BOT_TOKEN="ваш_токен"

   # Linux / macOS
   export BOT_TOKEN="ваш_токен"
   ```

4. Запустите бота:
   ```bash
   python bot.py
   ```

## Структура проекта
```
telegram-bot/
├── bot.py            # основной код бота
├── requirements.txt  # зависимости
└── requests.db       # база данных (создаётся автоматически)
```

## Скриншот работы
![Скриншот бота](screenshot.png)

## Автор
[GitHub](https://github.com/progerman666)
"""

# ============ Сохраняем файлы ============
with open("./output/bot.py", "w", encoding="utf-8") as f:
    f.write(bot_py)
with open("./output/requirements.txt", "w", encoding="utf-8") as f:
    f.write(requirements)
with open("./output/README.md", "w", encoding="utf-8") as f:
    f.write(readme)

print("Файлы созданы:")
for fn in ["bot.py", "requirements.txt", "README.md"]:
    print("  • output/" + fn)

# Проверка синтаксиса
import ast
try:
    ast.parse(bot_py)
    print("\\n✅ Синтаксис bot.py корректен")
except SyntaxError as e:
    print("\\n❌ Ошибка синтаксиса:", e)
