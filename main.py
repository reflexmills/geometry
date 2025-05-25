import os
import random
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# Загрузка конфига
load_dotenv()
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Подключение БД
conn = sqlite3.connect('gd_cards.db')
cursor = conn.cursor()

# Инициализация БД
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    last_card_time INTEGER DEFAULT 0,
    collection_score INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    stars INTEGER,
    rarity TEXT,
    image_url TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
''')
conn.commit()

# Конфиг карт
RARITIES = {
    "Обычная": {"weight": 50, "emoji": "⚪"},
    "Редкая": {"weight": 25, "emoji": "🔵"},
    "Эпическая": {"weight": 15, "emoji": "🟣"},
    "Легендарная": {"weight": 8, "emoji": "🟡"},
    "Хроматическая": {"weight": 2, "emoji": "🌈"}
}

CARDS = [
    {"name": "Stereo Madness", "min_stars": 1, "max_stars": 3},
    {"name": "Theory of Everything", "min_stars": 4, "max_stars": 6},
    {"name": "Deadlocked", "min_stars": 7, "max_stars": 10},
    {"name": "Geometrical Dominator", "min_stars": 5, "max_stars": 8},
    {"name": "Secret Card", "min_stars": 10, "max_stars": 10, "secret": True}
]

# Клавиатуры
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎴 Получить карту"))
    builder.row(
        KeyboardButton(text="📦 Коллекция"),
        KeyboardButton(text="🏆 Топ игроков")
    )
    builder.row(KeyboardButton(text="👤 Профиль"))
    return builder.as_markup(resize_keyboard=True)

# Система карт
def generate_card():
    card = random.choice(CARDS)
    stars = random.randint(card["min_stars"], card["max_stars"])
    rarity = random.choices(
        list(RARITIES.keys()),
        weights=[r["weight"] for r in RARITIES.values()]
    )[0]
    
    # Секретная карта (2% шанс)
    if card.get("secret") and random.random() < 0.02:
        return {
            "name": "SECRET: All Geometry Dash",
            "stars": 10,
            "rarity": "Хроматическая",
            "image_url": "https://i.imgur.com/secret.jpg"
        }
    
    return {
        "name": card["name"],
        "stars": stars,
        "rarity": rarity,
        "image_url": f"https://i.imgur.com/{card['name'].lower().replace(' ', '')}.jpg"
    }

# Обработчики
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
        (user_id, username)
    )
    conn.commit()
    
    await message.answer_photo(
        photo="https://i.imgur.com/gd_welcome.jpg",
        caption=f"🎮 Привет, {username}!\n\n"
               "Это бот для коллекционирования карт из Geometry Dash!\n"
               "Получай карты уровней и соревнуйся с другими игроками.",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "🎴 Получить карту")
async def get_card(message: types.Message):
    user_id = message.from_user.id
    
   # Проверка таймера (4 часа)
    cursor.execute('SELECT last_card_time FROM users WHERE user_id = ?', (user_id,))
    last_time = cursor.fetchone()[0]
    
    if time.time() - last_time < 4 * 3600:
        wait_time = int(4 * 3600 - (time.time() - last_time))
        hours = wait_time // 3600
        mins = (wait_time % 3600) // 60
        await message.answer(
            f"⏳ Следующая карта будет доступна через {hours}ч {mins}мин",
            reply_markup=main_keyboard()
        )
        return
    
    # Генерация карты
    card = generate_card()
    
    # Сохранение
    cursor.execute(
        'INSERT INTO cards (user_id, name, stars, rarity, image_url) VALUES (?, ?, ?, ?, ?)',
        (user_id, card["name"], card["stars"], card["rarity"], card["image_url"])
    )
    cursor.execute(
        'UPDATE users SET last_card_time = ?, collection_score = collection_score + ? WHERE user_id = ?',
        (int(time.time()), card["stars"], user_id)
    )
    conn.commit()
    
    # Отправка
    rarity_emoji = RARITIES[card["rarity"]]["emoji"]
    await message.answer_photo(
        photo=card["image_url"],
        caption=f"🎴 Новая карта!\n\n"
               f"▸ {card['name']}\n"
               f"▸ {rarity_emoji} {card['rarity']}\n"
               f"▸ ⭐ {card['stars']}/10\n\n"
               f"Следующая карта через 4 часа",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "📦 Коллекция")
async def show_collection(message: types.Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT rarity, COUNT(*), SUM(stars) 
        FROM cards 
        WHERE user_id = ?
        GROUP BY rarity
    ''', (user_id,))
    
    stats = cursor.fetchall()
    if not stats:
        await message.answer("Ваша коллекция пуста!", reply_markup=main_keyboard())
        return
    
    text = "📦 Ваша коллекция:\n\n"
    total_cards = 0
    total_score = 0
    
    for rarity, count, score in stats:
        emoji = RARITIES[rarity]["emoji"]
        text += f"{emoji} {rarity}: {count} карт (⭐ {score})\n"
        total_cards += count
        total_score += score or 0
    
    text += f"\nВсего: {total_cards} карт | Очки: {total_score}"
    await message.answer(text, reply_markup=main_keyboard())

@dp.message(F.text == "🏆 Топ игроков")
async def leaderboard(message: types.Message):
    cursor.execute('''
        SELECT username, COUNT(cards.card_id) as count, SUM(cards.stars) as score
        FROM users
        LEFT JOIN cards ON users.user_id = cards.user_id
        GROUP BY users.user_id
        ORDER BY score DESC
        LIMIT 10
    ''')
    
    top = cursor.fetchall()
    text = "🏆 Топ игроков:\n\n"
    
    for i, (name, cards, score) in enumerate(top, 1):
        text += f"{i}. {name}: {cards} карт (⭐ {score})\n"
    
    await message.answer(text, reply_markup=main_keyboard())

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT 
            username,
            (SELECT COUNT(*) FROM cards WHERE user_id = ?),
            (SELECT SUM(stars) FROM cards WHERE user_id = ?),
            (SELECT COUNT(DISTINCT name) FROM cards WHERE user_id = ?)
        FROM users
        WHERE user_id = ?
    ''', (user_id, user_id, user_id, user_id))
    
    username, total_cards, total_score, unique_cards = cursor.fetchone()
    
    await message.answer(
        f"👤 {username}\n\n"
        f"▸ Всего карт: {total_cards}\n"
        f"▸ Уникальных: {unique_cards}\n"
        f"▸ Очки коллекции: ⭐ {total_score or 0}\n\n"
        f"Редкости: {', '.join(RARITIES.keys())}",
        reply_markup=main_keyboard()
    )

if __name__ == '__main__':
    import asyncio
    asyncio.run(dp.start_polling(bot))
