import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq

from database import Database

AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 1700689138

current_model = "llama-3.3-70b-versatile"

ai_client = Groq(api_key=AI_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

logging.basicConfig(level=logging.INFO)

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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🛡\n\n"
        f"Система 'КиберЩит' готова к работе. Я — ваш автономный ИИ-эксперт по анализу угроз.\n\n"
        f"🔍 **Что делать?**\n"
        f"Пришлите или перешлите мне подозрительное сообщение, и я проведу глубокий аудит на предмет фишинга и социальной инженерии.\n\n"
        f"Берегите свои данные.\n\n#КиберПраво"
    )

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    kb = [
        [types.KeyboardButton(text="Модель: Llama 70B (Стандарт)")],
        [types.KeyboardButton(text="Модель: GPT 120B (Ультра)")],
        [types.KeyboardButton(text="Модель: Llama 17B (Массовая)")],
        [types.KeyboardButton(text="Скрыть панель")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(f"🔧 Панель управления активирована.\nТекущая модель: {current_model}", reply_markup=keyboard)

@dp.message(F.text == "Модель: Llama 70B (Стандарт)", F.from_user.id == ADMIN_ID)
async def set_llama70b(message: types.Message):
    global current_model
    current_model = "llama-3.3-70b-versatile"
    await message.answer("✅ Установлена основная модель Llama 3.3 70B (Стандарт качества).")

@dp.message(F.text == "Модель: GPT 120B (Ультра)", F.from_user.id == ADMIN_ID)
async def set_gpt120b(message: types.Message):
    global current_model
    current_model = "openai/gpt-oss-120b"
    await message.answer("🧠 Установлена экспертная модель GPT-OSS 120B (Ультра-анализ).")

@dp.message(F.text == "Модель: Llama 17B (Массовая)", F.from_user.id == ADMIN_ID)
async def set_qwen32b(message: types.Message):
    global current_model
    current_model = "meta-llama/llama-4-scout-17b-16e-instruct"
    await message.answer("🛡 Установлена дисциплинированная модель Llama 4-Scout 17B.")

@dp.message(F.text == "Скрыть панель", F.from_user.id == ADMIN_ID)
async def hide_panel(message: types.Message):
    await message.answer("Панель скрыта. Бот работает в штатном режиме.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(F.text)
async def message_handler(message: types.Message):
    status_message = await message.answer("Выполняю глубокое сканирование...")
    ai_response = await get_ai_answer(message.text)
    
    # Пытаемся достать username, если его нет — берем имя
    user_name = message.from_user.username or message.from_user.first_name
    
    # Сохраняем запрос и ответ в базу данных (теперь с именем)
    db.log_request(message.from_user.id, user_name, message.text, ai_response)
    
    await status_message.edit_text(ai_response)

async def main():
    print("--- Бот готов к работе ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())