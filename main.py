import os
import random
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Загрузка токена из .env
load_dotenv()
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Подключение к БД
conn = sqlite3.connect('gd_cards.db')
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    cards_collected INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    stars INTEGER,
    rarity TEXT,
    image_path TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
''')
conn.commit()

# Данные карт
CARDS_DATA = [
    {"name": "Stereo Madness", "min_stars": 1, "max_stars": 3, "rarity_weights": [70, 20, 8, 2]},
    {"name": "Theory of Everything", "min_stars": 4, "max_stars": 7, "rarity_weights": [50, 30, 15, 5]},
    {"name": "Deadlocked", "min_stars": 8, "max_stars": 10, "rarity_weights": [30, 40, 20, 10]}
]

RARITIES = ["Обычная", "Редкая", "Эпическая", "Легендарная"]

# Клавиатуры
def get_main_kb():
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="🎴 Получить карту", callback_data="get_card"))
    kb.add(types.InlineKeyboardButton(text="📦 Моя коллекция", callback_data="my_collection"))
    kb.add(types.InlineKeyboardButton(text="🏆 Таблица лидеров", callback_data="leaderboard"))
    kb.add(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    return kb.as_markup()

# Обработчики
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Регистрация пользователя
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    
    await message.answer(
        f"🎮 Добро пожаловать в GD Cards, {username}!\n"
        "Собирай карты уровней из Geometry Dash и соревнуйся с другими игроками!",
        reply_markup=get_main_kb()
    )

@dp.callback_query(F.data == "get_card")
async def get_card(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Выбираем случайную карту
    card_data = random.choice(CARDS_DATA)
    stars = random.randint(card_data["min_stars"], card_data["max_stars"])
    rarity = random.choices(RARITIES, weights=card_data["rarity_weights"])[0]
    
    # Сохраняем карту
    image_path = f"cards/{card_data['name'].lower().replace(' ', '_')}.jpg"
    cursor.execute(
        'INSERT INTO cards (user_id, name, stars, rarity, image_path) VALUES (?, ?, ?, ?, ?)',
        (user_id, card_data["name"], stars, rarity, image_path)
    )
    cursor.execute('UPDATE users SET cards_collected = cards_collected + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    
    # Отправляем карту
    try:
        photo = FSInputFile(image_path)
        await callback.message.answer_photo(
            photo,
            caption=f"🎴 Вы получили: {card_data['name']}\n"
                   f"⭐ Уровень: {stars}\n"
                   f"💎 Редкость: {rarity}"
        )
    except:
        await callback.message.answer(
            f"🎴 Вы получили: {card_data['name']}\n"
            f"⭐ Уровень: {stars}\n"
            f"💎 Редкость: {rarity}\n"
            f"🖼️ Изображение временно недоступно"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "my_collection")
async def show_collection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute('SELECT name, stars, rarity FROM cards WHERE user_id = ?', (user_id,))
    cards = cursor.fetchall()
    
    if not cards:
        await callback.message.answer("Ваша коллекция пуста!")
        return
    
    text = "📦 Ваша коллекция:\n\n"
    for card in cards:
        text += f"{card[0]} ⭐{card[1]} ({card[2]})\n"
    
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def show_leaderboard(callback: types.CallbackQuery):
    cursor.execute('SELECT username, cards_collected FROM users ORDER BY cards_collected DESC LIMIT 10')
    top_users = cursor.fetchall()
    
    text = "🏆 Топ-10 игроков:\n\n"
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user[0]}: {user[1]} карт\n"
    
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute('SELECT username, cards_collected FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM cards WHERE user_id = ?', (user_id,))
    total_cards = cursor.fetchone()[0]
    
    await callback.message.answer(
        f"👤 Профиль: {user[0]}\n"
        f"🎴 Карт получено: {total_cards}\n"
        f"🏅 Всего карт: {user[1]}"
    )
    await callback.answer()

if __name__ == '__main__':
    from aiogram.enums import ParseMode
    import asyncio
    
    async def main():
        await dp.start_polling(bot)
    
    asyncio.run(main())
