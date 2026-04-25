import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from groq import Groq

from config import MESSAGES, SETTINGS, PROMPTS
from database import Database

# --- SETTINGS ---
ADMIN_ID = 1111111111
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- INITIALIZATION ---
logging.basicConfig(level=logging.INFO)

ai_client = Groq(api_key=AI_KEY)
db = Database()
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

states = {"current_model": SETTINGS.MOD_L17}


# --- UI BUILDERS ---
def get_mode_kb():
    """Генерирует инлайн-клавиатуру на основе словаря MODE_NAMES из конфига."""
    builder = InlineKeyboardBuilder()
    
    # Проходим циклом по всем режимам, которые ты прописал в MESSAGES.MODE_NAMES
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(
            text=pretty_name, 
            callback_data=f"setmode_{code}"
        )
    
    # Выстраиваем по 1 или 2 кнопки в ряд (как тебе больше нравится)
    builder.adjust(1) 
    return builder.as_markup()

# --- AI LOGIC ---
async def get_ai_answer(user_text: str, mode: str) -> str:
    """Request to Groq API using the selected mode prompt."""
    instruction = PROMPTS.get(mode, PROMPTS["general"])
    
    try:
        completion = ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text}
            ],
            temperature=0.33,
            max_tokens=550
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq API Error: {e}")
        return f"AI System Error: {e}"


# --- USER COMMAND HANDLERS ---
@dp.message(Command("start", "st"))
async def start_handler(message: types.Message):
    await message.answer(
        MESSAGES.START.format(name=message.from_user.first_name),
        reply_markup=get_mode_kb()
    )


@dp.callback_query(F.data.startswith("setmode_"))
async def handle_mode_callback(callback: types.CallbackQuery):
    """Handles inline button clicks for mode selection."""
    new_mode = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    db.set_user_mode(user_id, new_mode)
    
    # Получаем красивое название из словаря
    pretty_mode = MESSAGES.MODE_NAMES.get(new_mode, "Неизвестный")
    
    try:
        await callback.message.edit_text(
            MESSAGES.MODE_CHANGED.format(mode=pretty_mode),
            reply_markup=get_mode_kb()
        )
    except Exception as e:
        logging.info(f"Message not modified: {e}")
    
    await callback.answer()

# --- ADMIN HANDLERS ---
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


@dp.message(F.from_user.id == ADMIN_ID, F.text.in_({SETTINGS.BTN_70B, SETTINGS.BTN_120B, SETTINGS.BTN_17B}))
async def change_model(message: types.Message):
    """Universal handler for model switching."""
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


# --- MAIN ANALYZER ---
@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    user_input = message.text or message.caption
    if not user_input:
        return

    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    # 1. Get user mode from database
    current_mode = db.get_user_mode(user_id)
    pretty_mode = MESSAGES.MODE_NAMES.get(current_mode, MESSAGES.MODE_NAMES["general"])
    # 2. Show scanning status with current mode
    status_msg = await message.answer(f"[{pretty_mode}] {MESSAGES.SCANNING}")
    
    # 3. Get AI response
    ai_response = await get_ai_answer(user_input, current_mode)
    
    # 4. Log everything to database
    db.log_request(user_id, user_name, user_input, ai_response, current_mode)
    
    # 5. Display result
    await status_msg.edit_text(ai_response)

    # 6. Notify admin
    if user_id != ADMIN_ID:
        report = (
            f"🔔 <b>Пользователь:</b> <code>{user_name}</code> (<code>{user_id}</code>)\n"
            f"⚙️ <b>Режим:</b> {current_mode.upper()}\n"
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