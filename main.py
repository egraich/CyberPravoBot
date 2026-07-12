import asyncio
import logging
import os
import re
import base64
import aiohttp

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from groq import AsyncGroq

# --- Local modules ---
from config import MESSAGES, SETTINGS, PROMPTS
from database import Database
from dotenv import load_dotenv

# --- CREDENTIALS & CONSTANTS ---
load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
AI_KEY = os.getenv("AI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY")

# --- INITIALIZATION ---
logging.basicConfig(level=logging.INFO)

ai_client = AsyncGroq(api_key=AI_KEY)
db = Database()

bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

states = {"current_model": SETTINGS.MOD_L17}

http_session: aiohttp.ClientSession = None

# --- UTILITY FUNCTIONS ---

async def extract_url(message: types.Message) -> str | None:
    """
    Finds and extracts the first valid URL in the text or caption using Telegram entities.
    Falls back to a robust regex if no entities are found.
    """
    text = message.text or message.caption
    if not text:
        return None
        
    entities = message.entities or message.caption_entities
    
    if entities:
        for entity in entities:
            if entity.type == "text_link":
                return entity.url
            if entity.type == "url":
                return text[entity.offset : entity.offset + entity.length]
    
    url_pattern = re.compile(r'https?://[^\s()<>]+(?:\([\w\d]+\)|[^.,;:\s])')
    match = url_pattern.search(text)
    
    return match.group(0) if match else None

async def scan_url_virustotal(url: str) -> str:
    """
    Asynchronously scans a URL using the VirusTotal API v3 via aiohttp.
    Returns a localized string from configuration containing the scan results.
    """
    if not VT_API_KEY:
        logging.error("VT: API Key is missing in environment variables!")
        return MESSAGES.VT_NO_KEY
    
    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    
    headers = {
        "x-apikey": VT_API_KEY, 
        "Accept": "application/json",
        "User-Agent": "CyberShieldBot/1.0"
    }
    
    try:
        logging.info(f"VT: Attempting to scan {url} (ID: {url_id})")
        async with http_session.get(api_url, headers=headers, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                stats = data['data']['attributes']['last_analysis_stats']
                malicious = stats.get('malicious', 0) + stats.get('suspicious', 0)
                total = sum(stats.values())
                
                logging.info(f"VT: Response successful for {url_id}")
                if malicious > 0:
                    return MESSAGES.VT_THREAT.format(malicious=malicious, total=total)
                return MESSAGES.VT_CLEAN.format(total=total)
            
            error_text = await response.text()
            logging.error(f"VT HTTP Error {response.status}: {error_text}")
            
            if response.status == 404:
                return MESSAGES.VT_NOT_FOUND
            if response.status == 401:
                return MESSAGES.VT_AUTH_ERROR
            if response.status == 429:
                return MESSAGES.VT_RATE_LIMIT
            
            return MESSAGES.VT_ERROR.format(code=response.status)
                
    except asyncio.TimeoutError:
        logging.error("VT: Request timed out.")
        return MESSAGES.VT_TIMEOUT
    except aiohttp.ClientError as e:
        logging.error(f"VT Connection Error: {e}")
        return MESSAGES.VT_CONNECTION_ERROR
    except Exception as e:
        logging.exception("VT Unexpected Exception")
        return MESSAGES.VT_UNEXPECTED_ERROR.format(error=type(e).__name__)

# --- KEYBOARD BUILDERS ---

def get_mode_kb() -> types.InlineKeyboardMarkup:
    """Dynamically builds the inline keyboard for mode selection based on config."""
    builder = InlineKeyboardBuilder()
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(text=pretty_name, callback_data=f"mode_{code}")
    builder.adjust(1) 
    return builder.as_markup()

# --- AI INTEGRATION ---

async def get_ai_answer(user_text: str, mode: str, vt_data: str = None) -> str:
    """Sends an asynchronous request to the Groq API using the selected analysis protocol."""
    instruction = PROMPTS.get(mode, PROMPTS["general"])
    messages = [{"role": "system", "content": instruction}]
    
    if vt_data:
        vt_system_msg = MESSAGES.VT_SYSTEM_PROMPT.format(vt_data=vt_data)
        messages.append({"role": "system", "content": vt_system_msg})
        
    messages.append({"role": "user", "content": user_text})
    
    try:
        completion = await ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=messages,
            temperature=0.33,
            max_tokens=600
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq API Error: {e}")
        return MESSAGES.AI_ERROR.format(error=e)

# --- COMMAND HANDLERS ---

@dp.message(Command("start", "st"))
async def start_handler(message: types.Message):
    """Handles the /start command, sending a welcome banner and the mode selection menu."""
    START_PHOTO_ID = "AgACAgIAAxkBAAIIVWoAAdBfCBRzpozezoFosa8YXrIwbgACRhhrG4QQCEgGn5dtYsTd0gEAAwIAA3kAAzsE" 
    
    await message.answer_photo(
        photo=START_PHOTO_ID,
        caption=MESSAGES.START, 
        reply_markup=get_mode_kb()
    )

@dp.callback_query(F.data.startswith("mode_"))
async def mode_callback_handler(callback: types.CallbackQuery):
    """Handles inline keyboard clicks for updating the active scanning profile."""
    await callback.answer()
    new_mode_code = callback.data.split("_")[1]
    await db.set_user_mode(callback.from_user.id, new_mode_code)
    
    pretty_name = MESSAGES.MODE_NAMES.get(new_mode_code, new_mode_code.upper())
    new_text = MESSAGES.MODE_CHANGED.format(mode=pretty_name)
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=new_text,
                reply_markup=get_mode_kb()
            )
        else:
            await callback.message.edit_text(
                text=new_text,
                reply_markup=get_mode_kb()
            )
    except Exception as e:
        logging.error(f"Message edit error: {e}")

# --- ADMINISTRATOR PANEL ---

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    """Activates the hidden admin panel for real-time model management and DB exports."""
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
    """Updates the global LLM target based on admin input."""
    if message.text == SETTINGS.BTN_70B:
        states["current_model"] = SETTINGS.MOD_L70
    elif message.text == SETTINGS.BTN_120B:
        states["current_model"] = SETTINGS.MOD_G120
    else:
        states["current_model"] = SETTINGS.MOD_L17
        
    await db.set_setting("current_model", states["current_model"])
    await message.answer(MESSAGES.MODEL_SET.format(model=message.text))

@dp.message(F.text == SETTINGS.BTN_HIDE, F.from_user.id == ADMIN_ID)
async def hide_panel(message: types.Message):
    """Dismisses the admin keyboard interface."""
    await message.answer(MESSAGES.ADMIN_HIDE, reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == SETTINGS.BTN_EXPORT, F.from_user.id == ADMIN_ID)
async def export_db_handler(message: types.Message):
    """Exports and sends the current SQLite database payload to the admin."""
    if os.path.exists(db.db_path):
        await message.answer_document(FSInputFile(db.db_path), caption=MESSAGES.DB_CAPTION)
    else:
        await message.answer(MESSAGES.DB_NOT_FOUND)

# --- MESSAGE HANDLERS ---

@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    """
    Primary processing pipeline. 
    Routes payloads to VT and/or LLM depending on the detection of embedded URLs.
    """
    raw_text = message.text or message.caption
    if not raw_text:
        return

    user_input = raw_text 
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    current_mode = await db.get_user_mode(user_id)
    pretty_mode = MESSAGES.MODE_NAMES.get(current_mode, "Standard")
    
    status_msg = await message.answer(MESSAGES.SCANNING.format(mode=pretty_mode))
    
    found_url = await extract_url(message)
    text_without_url = user_input.replace(found_url, '').strip() if found_url else user_input
    
    vt_result = None
    if found_url:
        logging.info(f"DEBUG: URL detected: {found_url}. Initiating VT scan...")
        vt_result = await scan_url_virustotal(found_url)
    else:
        logging.info("DEBUG: No URL detected in the payload.")

    if found_url and len(text_without_url) < 10:
        final_response = vt_result
    elif not found_url:

        final_response = await get_ai_answer(user_input, current_mode)
    else:

        ai_response = await get_ai_answer(user_input, current_mode, vt_data=vt_result)
        final_response = f"{ai_response}\n\n{vt_result}"

    try:
        await status_msg.edit_text(final_response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"HTML Formatting Error: {e}")
        await status_msg.edit_text(final_response, parse_mode=None)
            
    await db.log_request(user_id, user_name, user_input, final_response, current_mode)

    if user_id != ADMIN_ID:
        report = MESSAGES.ADMIN_REPORT.format(
            user_name=user_name,
            mode=current_mode,
            has_url='Yes' if found_url else 'No',
            text=user_input,
            response=final_response
        )
        try:
            await bot.send_message(ADMIN_ID, report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.error(f"Failed to dispatch admin report: {e}")

async def main():
    """Application entry point and core loop initialization."""
    global http_session
    logging.info("--- CyberShield System Initializing ---")
    await db.init_db()

    saved_model = await db.get_setting("current_model", SETTINGS.MOD_L17)
    states["current_model"] = saved_model
    logging.info(f"Loaded active AI model from DB: {saved_model}")
    
    async with aiohttp.ClientSession() as session:
        http_session = session
        await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("System gracefully halted by user")