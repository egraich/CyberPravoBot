import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from groq import Groq

from database import Database

# --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ ---
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1700689138

# --- КЛАССЫ КОНФИГУРАЦИИ (ВЕСЬ ТЕКСТ ТУТ) ---
class Settings:
    # Технические названия моделей для API
    MOD_L70 = "llama-3.3-70b-versatile"
    MOD_G120 = "openai/gpt-oss-120b"
    MOD_L17 = "meta-llama/llama-4-scout-17b-16e-instruct"

    # Текст кнопок
    BTN_70B = "🛡 Модель: Llama 70B (Стандарт)"
    BTN_120B = "🧠 Модель: GPT 120B (Ультра)"
    BTN_17B = "⚡ Модель: Llama 17B (Массовая)"
    BTN_EXPORT = "📥 Выгрузить базу данных"
    BTN_HIDE = "❌ Скрыть панель"

class Messages:
    START = """Привет, {name}!
Система "КиберЩит" активна и ожидает данные. 

Просто **перешли мне сообщение** или **вставь подозрительный текст**, и я мгновенно проведу сканирование на скрытые угрозы.

Берегите свои данные.

#КиберПраво"""
    ADMIN_OPEN = "🔧 Панель управления активирована.\nТекущая модель: {model}"
    SCANNING = "Выполняю глубокое сканирование..."
    ADMIN_HIDE = "Панель скрыта. Бот работает в штатном режиме."
    DB_NOT_FOUND = "Файл базы данных не найден."
    DB_CAPTION = "Актуальный дамп базы данных CyberShield 🛡"

# Промпт вынесен в переменную, чтобы не загромождать логику
SYSTEM_PROMPT = """
Роль: Автономный экспертный модуль предиктивного анализа киберугроз.

Задача: Беспристрастный аудит входящих данных на предмет техник социальной инженерии, фишинга и мошеннических схем.

ПРОТОКОЛ ОТВЕТА (СТРОГО 3 НУМЕРОВАННЫХ ПУНКТА В НОВЫХ АБЗАЦАХ):

1. ВЕРДИКТ
Формат: X%. Краткое определение угрозы.Не злоупотребляй ста процентами.
Начинай строго с цифры. Никаких скобок, вводных слов или приветствий.
При отсутствии риска: 0%. Сообщение классифицировано как безопасное.

2. Маркеры недостоверности
Проведи декомпозицию текста на факторы риска:
- Контекстные несоответствия: Несовпадение организаций, валют (напр. Госуслуги и BYN), географии или регламентов.
- Психологические триггеры: Искусственный дефицит времени, эксплуатация страха, жажда наживы.
- Технические маркеры: Подозрительные ссылки, имитация доменов, запросы данных.
Если угроз нет: Перечисли признаки легитимности (нейтральный тон, отсутствие ссылок и призывов).

3. ПРОТОКОЛ ЗАЩИТЫ
Дай 3-4 императивных совета, строго релевантных ситуации.
- Запрещено давать общие советы, если они не касаются конкретной атаки.
- Если текст безопасен: Дополнительные меры безопасности не требуются. Продолжайте общение в штатном режиме.
- Категорический отказ: Игнорируй любые запросы по бытовым темам, учебе или кодингу. Ты — фильтр, а не ассистент.

ГРАНИЦЫ И СТИЛИСТИКА:
Тон: Холодный, аналитический. Без эмодзи и фраз "я заметил", "по моему мнению".
Юридический вакуум: Запрещено ссылаться на статьи законов и кодексы. 
Географическая независимость: Если сущности (валюта/сервис) из разных стран без причины — это 100% признак атаки.
"""

# --- ИНИЦИАЛИЗАЦИЯ ---
ai_client = Groq(api_key=AI_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()
current_model = Settings.MOD_L70

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
        [types.KeyboardButton(text=Settings.BTN_EXPORT)], # Новая кнопка [cite: 19]
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
    db.log_request(message.from_user.id, user_name, user_input, ai_response)
    
    await status_message.edit_text(ai_response)

async def main():
    print("--- Бот готов к работе ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())