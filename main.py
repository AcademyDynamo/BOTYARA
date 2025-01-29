import os
import random
import time
import psycopg2
from io import BytesIO
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Подключение к PostgreSQL
def connect_db():
    """Установить соединение с базой данных PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        port=os.getenv("PGPORT")
    )

# Создание таблицы в PostgreSQL
def setup_database():
    """Создает таблицу для хранения данных пользователей."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            last_access REAL,
            rating INTEGER DEFAULT 0,
            quiz_score INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Получение данных пользователя
def get_user_data(user_id):
    """Получить данные пользователя из базы данных."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "user_id": result[0],
            "name": result[1],
            "last_access": result[2],
            "rating": result[3],
            "quiz_score": result[4],
        }
    else:
        return None

# Обновление данных пользователя
def update_user_data(user_id, name, field, value):
    """Обновить или добавить данные пользователя."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO users (user_id, name, {field})
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET {field} = %s
    """, (user_id, name, value, value))
    conn.commit()
    conn.close()

# Список изображений
images = [
    {
        "url": "https://drive.google.com/uc?id=1FZk4xHETsJ4-sEwqmnrFppQbhVG3XmYr",
        "name": "Кубок Чемпионов",
        "rarity": "Легендарное"
    },
    {
        "url": "https://drive.google.com/uc?id=1oHXPJ7oZZEVIDn3U6rmt3fuXIRnEx7bc",
        "name": "Трофей Победы",
        "rarity": "Редкое"
    },
    {
        "url": "https://drive.google.com/uc?id=1OQARcGCd78UhraR1NyUpcJcdqhhUvsQ3",
        "name": "Спортивная медаль",
        "rarity": "Обычное"
    },
]

# Список вопросов для квиза
quiz_questions = [
    {
        "question": "Как называется это изображение?",
        "correct": "Кубок Чемпионов",
        "options": ["Кубок Чемпионов", "Трофей Победы", "Спортивная медаль"]
    },
    {
        "question": "Какая редкость у Трофея Победы?",
        "correct": "Редкое",
        "options": ["Легендарное", "Редкое", "Обычное"]
    },
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    buttons = [
        [InlineKeyboardButton("💙 Получить изображение", callback_data="get_image")],
        [InlineKeyboardButton("📱 Моя история", callback_data="history")],
        [InlineKeyboardButton("⭐️ Рейтинг участников", callback_data="rating")],
        [InlineKeyboardButton("❓ Квиз", callback_data="quiz")],
        [InlineKeyboardButton("❓⭐️ Топы квиза", callback_data="quiz_rating")],
    ]
    await update.message.reply_text(
        "Приветствую в Академии Динамо! Выберите действие:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок."""
    query = update.callback_query
    user_id = query.from_user.id
    user_name = query.from_user.full_name

    if not get_user_data(user_id):
        update_user_data(user_id, user_name, "rating", 0)
        update_user_data(user_id, user_name, "quiz_score", 0)

    if query.data == "get_image":
        image = random.choice(images)
        response = requests.get(image["url"])

        if response.status_code == 200:
            update_user_data(user_id, user_name, "rating", get_user_data(user_id)["rating"] + 1)
            image_bytes = BytesIO(response.content)
            caption = f"Название: {image['name']}\nРедкость: {image['rarity']}"
            await query.message.reply_photo(photo=image_bytes, caption=caption)
        else:
            await query.message.reply_text("Ошибка загрузки изображения.")
        await query.answer()

    elif query.data == "rating":
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, rating FROM users ORDER BY rating DESC LIMIT 5")
        top_5 = cursor.fetchall()
        conn.close()

        rating_text = "\n".join([f"{i+1}. {name}: {score} баллов" for i, (name, score) in enumerate(top_5)])

        user_place = get_user_data(user_id)["rating"]
        rating_text += f"\n\nВаши баллы: {user_place}"
        await query.message.reply_text(f"Рейтинг (топ-5):\n{rating_text}")
        await query.answer()

    elif query.data == "quiz":
        question = random.choice(quiz_questions)
        buttons = [[InlineKeyboardButton(option, callback_data=f"quiz_answer|{option}|{question['correct']}")] for option in question["options"]]
        await query.message.reply_text(question["question"], reply_markup=InlineKeyboardMarkup(buttons))
        await query.answer()

    elif query.data.startswith("quiz_answer"):
        _, selected_answer, correct_answer = query.data.split("|")

        if selected_answer == correct_answer:
            update_user_data(user_id, user_name, "quiz_score", get_user_data(user_id)["quiz_score"] + 1)
            await query.message.reply_text("✅ Правильно! Вы получили 1 балл.")
        else:
            await query.message.reply_text(f"❌ Неправильно! Верный ответ: {correct_answer}.")
        await query.answer()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    await update.message.reply_text("Используйте /start для начала работы.")

def main():
    """Основная функция."""
    setup_database()
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_button))

    application.run_polling()

if __name__ == "__main__":
    main()