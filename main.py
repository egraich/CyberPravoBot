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

from config import MESSAGES, SETTINGS, PROMPTS
from database import Database

# --- SETTINGS ---
ADMIN_ID = 1111111111
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY") # Ключ от VirusTotal

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

# --- VIRUSTOTAL & UTILS ---
def extract_url(text: str) -> str:
    """Вытягивает первую найденную ссылку из текста."""
    url_pattern = re.compile(r'(https?://[^\s]+)')
    match = url_pattern.search(text)
    return match.group(1) if match else None

def scan_url_virustotal(url: str) -> str:
    """
    Легкий запрос к VT v3 API через встроенный urllib.
    Не жрет оперативку, не требует requests.
    """
    if not VT_API_KEY:
        return "<i>⚠️ API-ключ VirusTotal не настроен.</i>\n"
    
    # VT v3 требует Base64(url) без знаков '=' в конце
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    
    req = urllib.request.Request(api_url, headers={"x-apikey": VT_API_KEY})
    
    try:
        # Жесткий таймаут для спасения памяти, если VT ляжет
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            stats = data['data']['attributes']['last_analysis_stats']
            
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            total = sum(stats.values())
            
            if malicious > 0 or suspicious > 0:
                return f"🚨 <b>VirusTotal: {malicious+suspicious}/{total}</b> антивирусов считают ссылку опасной!\n\n"
            else:
                return f"✅ <b>VirusTotal: {malicious}/{total}</b> угроз не обнаружено.\n\n"
                
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "🔍 <b>VirusTotal:</b> Ссылка ранее не проверялась в базах.\n\n"
        return f"⚠️ <b>VirusTotal Error:</b> Ошибка API ({e.code})\n\n"
    except Exception as e:
        logging.error(f"VT Error: {e}")
        return ""

# --- UI BUILDERS ---
def get_mode_kb():
    builder = InlineKeyboardBuilder()
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(text=pretty_name, callback_data=f"setmode_{code}")
    builder.adjust(1) 
    return builder.as_markup()

# --- AI LOGIC ---
async def get_ai_answer(user_text: str, mode: str) -> str:
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
    await message.answer(MESSAGES.START, reply_markup=get_mode_kb())

@dp.callback_query(F.data.startswith("setmode_"))
async def handle_mode_callback(callback: types.CallbackQuery):
    new_mode = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    db.set_user_mode(user_id, new_mode)
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

# --- MAIN ANALYZER ---
@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    raw_text = message.text or message.caption
    if not raw_text:
        return

    # Защита памяти: обрезаем слишком длинные тексты
    user_input = raw_text[:1500] 

    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    current_mode = db.get_user_mode(user_id)
    pretty_mode = MESSAGES.MODE_NAMES.get(current_mode, MESSAGES.MODE_NAMES["general"])
    
    status_msg = await message.answer(f"[{pretty_mode}] {MESSAGES.SCANNING}")
    
    # 1. Проверка на наличие URL
    extracted_url = extract_url(user_input)
    vt_result = ""
    if extracted_url:
        vt_result = scan_url_virustotal(extracted_url)
    
    # 2. ИИ-анализ текста
    ai_response = await get_ai_answer(user_input, current_mode)
    
    # 3. Формирование финального ответа (Плашка VT + ИИ)
    final_response = f"{vt_result}{ai_response}"
    
    db.log_request(user_id, user_name, user_input, ai_response, current_mode)
    
    # Используем None, так как ИИ выдает текст без HTML (согласно системному промпту)
    # Но если VT вернул HTML, AI-часть может отображаться как есть.
    await status_msg.edit_text(final_response, parse_mode=None)

    if user_id != ADMIN_ID:
        report = (
            f"🔔 <b>Юзер:</b> <code>{user_name}</code>\n"
            f"⚙️ <b>Режим:</b> {current_mode.upper()}\n"
            f"🔗 <b>URL найден:</b> {'Да' if extracted_url else 'Нет'}\n"
            f"📥 <b>Сообщение:</b>\n<code>{user_input}</code>\n"
            f"{'—' * 15}\n"
            f"🛡 <b>Ответ:</b>\n\n{final_response}"
        )
        try:
            await bot.send_message(ADMIN_ID, report[:4000]) # Ограничение для админа
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