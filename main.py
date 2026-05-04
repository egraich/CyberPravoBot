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

# Твои локальные модули
from config import MESSAGES, SETTINGS, PROMPTS
from database import Database

# --- НАСТРОЙКИ И КЛЮЧИ ---
ADMIN_ID = 1111111111
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY")  # Ключ от VirusTotal

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (УТИЛИТЫ) ---

def extract_url(text: str) -> str:
    """
    Ищет первую ссылку в тексте сообщения с помощью регулярного выражения.
    """
    url_pattern = re.compile(r'(https?://[^\s]+)')
    match = url_pattern.search(text)
    return match.group(1) if match else None

def scan_url_virustotal(url: str) -> str:
    """
    Проверяет ссылку через VirusTotal API v3.
    Использует стандартный urllib, чтобы не раздувать зависимости.
    """
    if not VT_API_KEY:
        return "<em>⚠️ Ошибка: Ключ VirusTotal не найден в системе.</em>\n"
    
    # API VT v3 требует ID в формате Base64 без символов '='
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    
    req = urllib.request.Request(api_url, headers={"x-apikey": VT_API_KEY})
    
    try:
        # Ставим таймаут 5 сек, чтобы не вешать бота при лагах VT
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            stats = data['data']['attributes']['last_analysis_stats']
            
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            total = sum(stats.values())
            
            if malicious > 0 or suspicious > 0:
                return f"🚨 <b>VirusTotal: {malicious+suspicious}/{total}</b> антивирусов нашли угрозу!\n\n"
            else:
                return f"✅ <b>VirusTotal:</b> В базах чисто (0/{total}).\n\n"
                
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "🔍 <b>VirusTotal:</b> Этой ссылки еще нет в базе. Будьте осторожны.\n\n"
        return f"⚠️ <b>VirusTotal:</b> Ошибка сервера ({e.code})\n\n"
    except Exception as e:
        logging.error(f"VT Error: {e}")
        return ""

# --- ЛОГИКА КЛАВИАТУР ---

def get_mode_kb():
    """
    Динамически собирает инлайн-кнопки режимов из MESSAGES.MODE_NAMES.
    """
    builder = InlineKeyboardBuilder()
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(text=pretty_name, callback_data=f"setmode_{code}")
    builder.adjust(1) 
    return builder.as_markup()

# --- ВЗАИМОДЕЙСТВИЕ С ИИ ---

async def get_ai_answer(user_text: str, mode: str) -> str:
    """
    Отправляет запрос в Groq (Llama) с учетом выбранного режима.
    """
    instruction = PROMPTS.get(mode, PROMPTS["general"])
    try:
        completion = ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text}
            ],
            temperature=0.33, # Низкая температура для точности вердикта
            max_tokens=600   # Лимит на длину ответа
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
    """Смена режима анализа по нажатию на кнопку."""
    new_mode = callback.data.split("_")[1]
    db.set_user_mode(callback.from_user.id, new_mode)
    
    pretty_mode = MESSAGES.MODE_NAMES.get(new_mode, "Стандарт")
    
    try:
        await callback.message.edit_text(
            MESSAGES.MODE_CHANGED.format(mode=pretty_mode),
            reply_markup=get_mode_kb()
        )
    except Exception:
        pass # Игнорим ошибку, если сообщение не изменилось
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

# --- ГЛАВНЫЙ АНАЛИЗАТОР ---

@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    """
    Основная логика: проверка на ссылки -> VT -> AI анализ -> логирование.
    """
    user_input = message.text or message.caption
    if not user_input:
        return
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    # Достаем текущий режим юзера
    current_mode = db.get_user_mode(user_id)
    pretty_mode = MESSAGES.MODE_NAMES.get(current_mode, "Стандарт")
    
    # Показываем статус сканирования
    status_msg = await message.answer(f"[{pretty_mode}] {MESSAGES.SCANNING}")
    
    # 1. Поиск и проверка ссылки через VirusTotal
    found_url = extract_url(user_input)
    vt_part = ""
    if found_url:
        vt_part = scan_url_virustotal(found_url)
    
    # 2. Получаем ИИ-вердикт
    ai_part = await get_ai_answer(user_input, current_mode)
    
    # 3. Сохраняем в историю
    db.log_request(user_id, user_name, user_input, ai_part, current_mode)
    
    # 4. Отправляем финальный результат (VT + AI)
    # parse_mode=None т.к. ИИ может выдать символы, которые сломают HTML
    await status_msg.edit_text(f"{vt_part}{ai_part}", parse_mode=None)

    # 5. Уведомление админа о действии юзера
    if user_id != ADMIN_ID:
        report = (
            f"🔔 Юзер: {user_name}\n"
            f"⚙️ Режим: {current_mode}\n"
            f"📥 Текст: {user_input[:200]}..."
        )
        try:
            await bot.send_message(ADMIN_ID, report)
        except Exception:
            pass

async def main():
    logging.info("--- Бот запущен и готов к защите ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен")