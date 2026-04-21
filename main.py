import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from groq import Groq
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import Settings, Messages, SYSTEM_PROMPT

from database import Database

# --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ ---
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1700689138
# --- ИНИЦИАЛИЗАЦИЯ ---
ai_client = Groq(api_key=AI_KEY)

bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
db = Database()
current_model = Settings.MOD_L17

logging.basicConfig(level=logging.INFO)

# --- ЛОГИКА ИИ ---
async def get_ai_answer(user_text):
    global current_model
    try:
        completion = ai_client.chat.completions.create(
            model=current_model, 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,
            max_tokens=550
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Ошибка системы ИИ: {e}"

# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(Messages.START.format(name=message.from_user.first_name))

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    kb = [
        [types.KeyboardButton(text=Settings.BTN_70B)],
        [types.KeyboardButton(text=Settings.BTN_120B)],
        [types.KeyboardButton(text=Settings.BTN_17B)],
        [types.KeyboardButton(text=Settings.BTN_EXPORT)],
        [types.KeyboardButton(text=Settings.BTN_HIDE)]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(Messages.ADMIN_OPEN.format(model=current_model), reply_markup=keyboard)

# --- АДМИНСКИЕ ХЕНДЛЕРЫ ---
@dp.message(F.text == Settings.BTN_70B, F.from_user.id == ADMIN_ID)
async def set_llama70b(message: types.Message):
    global current_model
    current_model = Settings.MOD_L70
    await message.answer(f"✅ Установлена модель: {Settings.BTN_70B}")

@dp.message(F.text == Settings.BTN_120B, F.from_user.id == ADMIN_ID)
async def set_gpt120b(message: types.Message):
    global current_model
    current_model = Settings.MOD_G120
    await message.answer(f"✅ Установлена модель: {Settings.BTN_120B}")

@dp.message(F.text == Settings.BTN_17B, F.from_user.id == ADMIN_ID)
async def set_llama17b(message: types.Message):
    global current_model
    current_model = Settings.MOD_L17
    await message.answer(f"✅ Установлена модель: {Settings.BTN_17B}")

@dp.message(F.text == Settings.BTN_HIDE, F.from_user.id == ADMIN_ID)
async def hide_panel(message: types.Message):
    await message.answer(Messages.ADMIN_HIDE, reply_markup=types.ReplyKeyboardRemove())

# ХЕНДЛЕР ВЫГРУЗКИ БД
@dp.message(F.text == Settings.BTN_EXPORT, F.from_user.id == ADMIN_ID)
async def export_db_handler(message: types.Message):
    if os.path.exists(db.db_path):
        file = FSInputFile(db.db_path)
        await message.answer_document(file, caption=Messages.DB_CAPTION)
    else:
        await message.answer(Messages.DB_NOT_FOUND)

# --- ГЛАВНЫЙ АНАЛИЗАТОР ---
@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    user_input = message.text or message.caption
    if not user_input: return

    status_message = await message.answer(Messages.SCANNING)
    ai_response = await get_ai_answer(user_input)
    
    user_name = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id
    
    db.log_request(user_id, user_name, user_input, ai_response)
    
    await status_message.edit_text(ai_response)

    # --- УВЕДОМЛЕНИЕ ДЛЯ АДМИНА ---
    if user_id != ADMIN_ID:
        admin_report = (
            f"🔔 <b>Пользователь:</b> <code>{user_name}<code> (<code>{user_id}</code>)\n"
            f"📥 <b>Сообщение:</b>\n <code>{user_input}</code>\n"
            f"--- --- --- --- ---\n"
            f"🛡 <b>Ответ ИИ:</b>\n\n"
            f"{ai_response}"
        )
        
        try:
            await bot.send_message(ADMIN_ID, admin_report)
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления админу: {e}")

async def main():
    print("--- Бот готов к работе ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())