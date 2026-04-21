import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from groq import Groq

from config import MESSAGES, SETTINGS, SYSTEM_PROMPT
from database import Database

# --- НАСТРОЙКИ (Константы пишем капсом) ---
ADMIN_ID = 1700689138
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)

ai_client = Groq(api_key=AI_KEY)
db = Database()
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Состояние модели (можно хранить в обычном словаре, чтобы избежать глобалок)
states = {"current_model": SETTINGS.MOD_L17}


# --- ЛОГИКА ИИ ---
async def get_ai_answer(user_text: str) -> str:
    """Запрос к API Groq для анализа текста."""
    try:
        completion = ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,
            max_tokens=550
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка Groq: {e}")
        return f"Ошибка системы ИИ: {e}"


# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(MESSAGES.START.format(name=message.from_user.first_name))


@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    kb = [
        [KeyboardButton(text=SETTINGS.BTN_70B)],
        [KeyboardButton(text=SETTINGS.BTN_120B)],
        [KeyboardButton(text=SETTINGS.BTN_17B)],
        [KeyboardButton(text=SETTINGS.BTN_EXPORT)],
        [KeyboardButton(text=SETTINGS.BTN_HIDE)]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        MESSAGES.ADMIN_OPEN.format(model=states["current_model"]), 
        reply_markup=keyboard
    )


# --- АДМИНСКИЕ ХЕНДЛЕРЫ ---
@dp.message(F.from_user.id == ADMIN_ID, F.text.in_({SETTINGS.BTN_70B, SETTINGS.BTN_120B, SETTINGS.BTN_17B}))
async def change_model(message: types.Message):
    """Универсальный хендлер для смены модели."""
    if message.text == SETTINGS.BTN_70B:
        states["current_model"] = SETTINGS.MOD_L70
    elif message.text == SETTINGS.BTN_120B:
        states["current_model"] = SETTINGS.MOD_G120
    else:
        states["current_model"] = SETTINGS.MOD_L17
    
    await message.answer(f"✅ Установлена модель: {message.text}")


@dp.message(F.text == SETTINGS.BTN_HIDE, F.from_user.id == ADMIN_ID)
async def hide_panel(message: types.Message):
    await message.answer(MESSAGES.ADMIN_HIDE, reply_markup=ReplyKeyboardRemove())


@dp.message(F.text == SETTINGS.BTN_EXPORT, F.from_user.id == ADMIN_ID)
async def export_db_handler(message: types.Message):
    if os.path.exists(db.db_path):
        await message.answer_document(
            FSInputFile(db.db_path), 
            caption=MESSAGES.DB_CAPTION
        )
    else:
        await message.answer(MESSAGES.DB_NOT_FOUND)


# --- ГЛАВНЫЙ АНАЛИЗАТОР ---
@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    user_input = message.text or message.caption
    if not user_input:
        return

    status_msg = await message.answer(MESSAGES.SCANNING)
    ai_response = await get_ai_answer(user_input)
    
    user_name = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    db.log_request(user_id, user_name, user_input, ai_response)
    await status_msg.edit_text(ai_response)

    # Уведомление админа
    if user_id != ADMIN_ID:
        report = (
            f"🔔 <b>Пользователь:</b> <code>{user_name}</code> (<code>{user_id}</code>)\n"
            f"📥 <b>Сообщение:</b>\n<code>{user_input}</code>\n"
            f"{'—' * 15}\n"
            f"🛡 <b>Ответ ИИ:</b>\n\n{ai_response}"
        )
        try:
            await bot.send_message(ADMIN_ID, report)
        except Exception as e:
            logging.error(f"Ошибка уведомления: {e}")


async def main():
    logging.info("--- Бот готов к работе ---")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот выключен")