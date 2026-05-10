import asyncio
import logging
import os
import re
import urllib.request
import urllib.error
import json
import base64

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from groq import Groq

# Подключение локальных модулей
from config import MESSAGES, SETTINGS, PROMPTS
from database import Database

# --- НАСТРОЙКИ И КЛЮЧИ ---
ADMIN_ID = 1111111111
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY")

# --- ИНИЦИАЛИЗАЦИЯ ОБЪЕКТОВ ---
logging.basicConfig(level=logging.INFO)

ai_client = Groq(api_key=AI_KEY)
db = Database()
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Храним текущую модель в памяти (для быстрой смены админом)
states = {"current_model": SETTINGS.MOD_L17}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def extract_url(text: str) -> str:
    """Ищет первую ссылку в тексте сообщения с помощью регулярного выражения."""
    url_pattern = re.compile(r'(https?://[^\s]+)')
    match = url_pattern.search(text)
    return match.group(1) if match else None

def scan_url_virustotal(url: str) -> str:
    if not VT_API_KEY:
        return MESSAGES.VT_NO_KEY
    
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    
    req = urllib.request.Request(
        api_url, 
        headers={"x-apikey": VT_API_KEY, "Accept": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            stats = data['data']['attributes']['last_analysis_stats']
            malicious = stats.get('malicious', 0) + stats.get('suspicious', 0)
            total = sum(stats.values())
            
            if malicious > 0:
                return MESSAGES.VT_THREAT.format(malicious=malicious, total=total)
            return MESSAGES.VT_CLEAN.format(total=total)
                
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return MESSAGES.VT_NOT_FOUND
        if e.code == 429:
            return "⚠️ <b>VirusTotal:</b> Лимит запросов (4/мин) исчерпан. Попробуйте позже."
        return MESSAGES.VT_ERROR.format(code=e.code)
    except Exception:
        return ""

# --- ЛОГИКА КЛАВИАТУР ---

def get_mode_kb():
    """Динамически собирает инлайн-кнопки режимов из config.py."""
    builder = InlineKeyboardBuilder()
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(text=pretty_name, callback_data=f"setmode_{code}")
    builder.adjust(1) 
    return builder.as_markup()

# --- ВЗАИМОДЕЙСТВИЕ С ИИ ---

async def get_ai_answer(user_text: str, mode: str, vt_data: str = None) -> str:
    """
    Отправляет запрос в Groq (Llama) с учетом выбранного режима.
    Если есть результаты VT (vt_data), передает их ИИ как системную директиву.
    """
    instruction = PROMPTS.get(mode, PROMPTS["general"])
    
    # Формируем базовый контекст
    messages = [{"role": "system", "content": instruction}]
    
    # Инъекция данных VirusTotal для ИИ (если ссылка была в сообщении)
    if vt_data:
        vt_system_msg = MESSAGES.VT_SYSTEM_PROMPT.format(vt_data=vt_data)
        messages.append({"role": "system", "content": vt_system_msg})
        
    messages.append({"role": "user", "content": user_text})
    
    try:
        completion = ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=messages,
            temperature=0.33,
            max_tokens=600
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq API Error: {e}")
        return f"Ошибка ИИ-анализа: {e}"

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start", "st"))
async def start_handler(message: types.Message):
    """Приветствие и выдача меню выбора режимов."""
    await message.answer(MESSAGES.START, reply_markup=get_mode_kb())

@dp.callback_query(F.data.startswith("setmode_"))
async def handle_mode_callback(callback: types.CallbackQuery):
    """Смена режима анализа по нажатию на инлайн-кнопку."""
    new_mode = callback.data.split("_")[1]
    db.set_user_mode(callback.from_user.id, new_mode)
    
    pretty_mode = MESSAGES.MODE_NAMES.get(new_mode, "Стандарт")
    
    try:
        await callback.message.edit_text(
            MESSAGES.MODE_CHANGED.format(mode=pretty_mode),
            reply_markup=get_mode_kb()
        )
    except Exception:
        pass
    await callback.answer()

# --- ПАНЕЛЬ АДМИНИСТРАТОРА ---

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    """Открывает скрытое меню для управления моделями и выгрузки БД."""
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
        await message.answer_document(FSInputFile(db.db_path), caption=MESSAGES.DB_CAPTION)
    else:
        await message.answer(MESSAGES.DB_NOT_FOUND)

# --- ГЛАВНЫЙ АНАЛИЗАТОР ---

@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    """
    Основная логика распределения нагрузки (Ссылка / Текст / Ссылка+Текст).
    """
    raw_text = message.text or message.caption
    if not raw_text:
        return

    # Защита от переполнения памяти сервера (обрезаем гигантские спам-сообщения)
    user_input = raw_text 

    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    current_mode = db.get_user_mode(user_id)
    pretty_mode = MESSAGES.MODE_NAMES.get(current_mode, "Стандарт")
    
    status_msg = await message.answer(f"[{pretty_mode}] {MESSAGES.SCANNING}")
    
    found_url = extract_url(user_input)
    text_without_url = user_input.replace(found_url, '').strip() if found_url else user_input
    
    # СЦЕНАРИЙ 1: В сообщении ТОЛЬКО ссылка (или текста меньше 10 символов)
    if found_url and len(text_without_url) < 10:
        vt_result = scan_url_virustotal(found_url)
        await status_msg.edit_text(vt_result, parse_mode=ParseMode.HTML)
        db.log_request(user_id, user_name, user_input, vt_result, current_mode)
        return

    # СЦЕНАРИЙ 2: В сообщении НЕТ ссылок (только текст)
    if not found_url:
        ai_response = await get_ai_answer(user_input, current_mode)
        # HTML не используем, чтобы Llama случайно не сломала разметку
        await status_msg.edit_text(ai_response, parse_mode=None)
        db.log_request(user_id, user_name, user_input, ai_response, current_mode)
        
    # СЦЕНАРИЙ 3: В сообщении есть И ССЫЛКА, И ТЕКСТ
    if found_url and len(text_without_url) >= 10:
        vt_result = scan_url_virustotal(found_url)
        ai_response = await get_ai_answer(user_input, current_mode, vt_data=vt_result)
        
        final_response = f"{ai_response}\n\n{vt_result}"
        
        try:
            # Пытаемся отправить с жирным текстом
            await status_msg.edit_text(final_response, parse_mode=ParseMode.HTML)
        except Exception:
            # Если ИИ прислал < или > и сломал HTML, отправляем как есть
            await status_msg.edit_text(final_response, parse_mode=None)
            
        db.log_request(user_id, user_name, user_input, final_response, current_mode)

    # --- Уведомление администратора ---
    if user_id != ADMIN_ID:
        report = MESSAGES.ADMIN_REPORT.format(
            user_name=user_name,
            mode=current_mode,
            has_url='Да' if found_url else 'Нет',
            text=user_input,
            response=ai_response if not found_url else final_response # Защита длины ответа
        )
        try:
            await bot.send_message(ADMIN_ID, report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.error(f"Ошибка отправки репорта: {e}")

async def main():
    logging.info("--- Система КиберЩит запущена ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Система остановлена")