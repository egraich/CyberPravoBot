# Copyright (c) 2026 egraich

import asyncio
import logging
import sys
import os
import re
import base64
import html
import aiohttp

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from groq import AsyncGroq
from dotenv import load_dotenv

from config import MESSAGES, SETTINGS, PROMPTS, LOG_MSGS
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("CyberShieldBot")

load_dotenv(override=False)
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY")

ai_client = AsyncGroq(api_key=GROQ_API_KEY)
db = Database()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

states = {"current_model": SETTINGS.MOD_L17}
http_session: aiohttp.ClientSession | None = None

async def extract_url(message: types.Message) -> str | None:
    """Parse valid URL from message entities or regex fallback"""
    text = message.text or message.caption
    if not text:
        return None
        
    entities = message.entities or message.caption_entities
    if entities:
        for entity in entities:
            if entity.type == "text_link":
                url = entity.url
                logger.debug(LOG_MSGS.URL_EXTRACTED.format(url=url))
                return url
            if entity.type == "url":
                url = text[entity.offset : entity.offset + entity.length]
                logger.debug(LOG_MSGS.URL_EXTRACTED.format(url=url))
                return url
    
    match = re.search(r'https?://[^\s()<>]+(?:\([\w\d]+\)|[^.,;:\s])', text)
    if match:
        logger.debug(LOG_MSGS.URL_EXTRACTED.format(url=match.group(0)))
        return match.group(0)
        
    logger.debug(LOG_MSGS.URL_NONE)
    return None

async def scan_url_virustotal(url: str) -> str:
    """Dispatch URL to VT API and return formatted state"""
    if not VT_API_KEY:
        logger.warning("VirusTotal API Key is missing.")
        return MESSAGES.VT_NO_KEY
    
    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    
    headers = {
        "x-apikey": VT_API_KEY, 
        "Accept": "application/json",
        "User-Agent": "CyberShieldBot/1.0"
    }
    
    logger.info(LOG_MSGS.VT_REQ_START.format(url_id=url_id))
    
    try:
        async with http_session.get(api_url, headers=headers, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                stats = data['data']['attributes']['last_analysis_stats']
                malicious = stats.get('malicious', 0) + stats.get('suspicious', 0)
                total = sum(stats.values())
                
                logger.info(LOG_MSGS.VT_SUCCESS.format(malicious=malicious, total=total))
                
                if malicious > 0:
                    return MESSAGES.VT_THREAT.format(malicious=malicious, total=total)
                return MESSAGES.VT_CLEAN.format(total=total)
            
            if response.status == 404:
                logger.info(LOG_MSGS.VT_NOT_FOUND)
                return MESSAGES.VT_NOT_FOUND
                
            logger.error(LOG_MSGS.VT_API_ERR.format(status=response.status))
            if response.status == 401:
                return MESSAGES.VT_AUTH_ERROR
            if response.status == 429:
                return MESSAGES.VT_RATE_LIMIT
            
            return MESSAGES.VT_ERROR.format(code=response.status)
                
    except asyncio.TimeoutError:
        logger.error("VirusTotal request timed out.")
        return MESSAGES.VT_TIMEOUT
    except aiohttp.ClientError as ce:
        logger.error(LOG_MSGS.VT_EXCEPTION.format(err=ce))
        return MESSAGES.VT_CONNECTION_ERROR
    except Exception as e:
        logger.error(LOG_MSGS.VT_EXCEPTION.format(err=e))
        return MESSAGES.VT_UNEXPECTED_ERROR.format(error=type(e).__name__)

def get_mode_kb() -> types.InlineKeyboardMarkup:
    """Build dynamic inline menu for modes"""
    builder = InlineKeyboardBuilder()
    for code, pretty_name in MESSAGES.MODE_NAMES.items():
        builder.button(text=pretty_name, callback_data=f"mode_{code}")
    builder.adjust(1) 
    return builder.as_markup()

async def get_ai_answer(user_text: str, mode: str, vt_data: str = None) -> str:
    """Request completion from selected LLM model"""
    logger.info(LOG_MSGS.AI_REQ_START.format(model=states["current_model"], mode=mode))
    
    messages = [{"role": "system", "content": PROMPTS.get(mode, PROMPTS["general"])}]
    
    if vt_data:
        messages.append({"role": "system", "content": MESSAGES.VT_SYSTEM_PROMPT.format(vt_data=vt_data)})
        
    messages.append({"role": "user", "content": user_text})
    
    try:
        completion = await ai_client.chat.completions.create(
            model=states["current_model"], 
            messages=messages,
            temperature=0.33,
            max_tokens=600
        )
        response_text = completion.choices[0].message.content
        logger.info(LOG_MSGS.AI_SUCCESS.format(length=len(response_text)))
        return response_text
    except Exception as e:
        logger.error(LOG_MSGS.AI_ERROR.format(err=e))
        return MESSAGES.AI_ERROR.format(error=e)

@dp.message(Command("start", "st"))
async def start_handler(message: types.Message):
    """Initial onboarding"""
    logger.info(LOG_MSGS.CMD_START.format(user_id=message.from_user.id))
    await message.answer_photo(
        photo=SETTINGS.START_PHOTO_ID,
        caption=MESSAGES.START, 
        reply_markup=get_mode_kb()
    )

@dp.callback_query(F.data.startswith("mode_"))
async def mode_callback_handler(callback: types.CallbackQuery):
    """Update user mode preferences"""
    new_mode = callback.data.split("_")[1]
    logger.info(LOG_MSGS.CMD_MODE_CHG.format(user_id=callback.from_user.id, mode=new_mode))
    
    await callback.answer()
    await db.set_user_mode(callback.from_user.id, new_mode)
    
    new_text = MESSAGES.MODE_CHANGED.format(mode=MESSAGES.MODE_NAMES.get(new_mode, new_mode))
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=new_text, reply_markup=get_mode_kb())
        else:
            await callback.message.edit_text(text=new_text, reply_markup=get_mode_kb())
    except Exception as e:
        logger.error(LOG_MSGS.MSG_REPLY_ERR.format(user_id=callback.from_user.id, err=e))

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    """Deploy admin keyboard"""
    logger.info(LOG_MSGS.ADMIN_PANEL.format(user_id=message.from_user.id))
    kb = [
        [KeyboardButton(text=SETTINGS.BTN_70B)],
        [KeyboardButton(text=SETTINGS.BTN_QCM)],
        [KeyboardButton(text=SETTINGS.BTN_17B)],
        [KeyboardButton(text=SETTINGS.BTN_EXPORT)],
        [KeyboardButton(text=SETTINGS.BTN_HIDE)]
    ]
    await message.answer(
        MESSAGES.ADMIN_OPEN.format(model=states["current_model"]), 
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )

@dp.message(F.from_user.id == ADMIN_ID, F.text.in_({SETTINGS.BTN_70B, SETTINGS.BTN_QCM, SETTINGS.BTN_17B}))
async def change_model(message: types.Message):
    """Hot-swap active LLM"""
    if message.text == SETTINGS.BTN_70B:
        states["current_model"] = SETTINGS.MOD_L70
    elif message.text == SETTINGS.BTN_QCM:
        states["current_model"] = SETTINGS.MOD_QCM
    else:
        states["current_model"] = SETTINGS.MOD_L17
        
    logger.info(LOG_MSGS.ADMIN_MDL_CHG.format(model=states["current_model"]))
    await db.set_setting("current_model", states["current_model"])
    await message.answer(MESSAGES.MODEL_SET.format(model=message.text))

@dp.message(F.text == SETTINGS.BTN_HIDE, F.from_user.id == ADMIN_ID)
async def hide_panel(message: types.Message):
    """Retract admin keyboard"""
    await message.answer(MESSAGES.ADMIN_HIDE, reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == SETTINGS.BTN_EXPORT, F.from_user.id == ADMIN_ID)
async def export_db_handler(message: types.Message):
    """Serve DB dump"""
    logger.info(LOG_MSGS.ADMIN_DB_EXP)
    if os.path.exists(db.db_path):
        await message.answer_document(FSInputFile(db.db_path), caption=MESSAGES.DB_CAPTION)
    else:
        await message.answer(MESSAGES.DB_NOT_FOUND)

@dp.message(F.text | F.caption)
async def message_handler(message: types.Message):
    """Main routing logic for scans"""
    user_input = message.text or message.caption
    if not user_input:
        return

    user_id = message.from_user.id
    logger.info(LOG_MSGS.MSG_PROCESSING.format(user_id=user_id, length=len(user_input)))
    
    user_name = message.from_user.username or message.from_user.first_name
    current_mode = await db.get_user_mode(user_id)
    
    status_msg = await message.answer(MESSAGES.SCANNING.format(mode=MESSAGES.MODE_NAMES.get(current_mode, "Стандарт")))
    found_url = await extract_url(message)
    
    vt_result = None
    if found_url:
        vt_result = await scan_url_virustotal(found_url)
        text_without_url = user_input.replace(found_url, "").strip()
        
        if text_without_url: 
            ai_response = await get_ai_answer(user_input, current_mode, vt_data=vt_result)
            final_response = f"{ai_response}\n\n{vt_result}"
        else:
            final_response = vt_result
    else:
        final_response = await get_ai_answer(user_input, current_mode)

    try:
        await status_msg.edit_text(final_response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Failed HTML parse on edit, fallback to clear text: {e}")
        try:
            await status_msg.edit_text(final_response, parse_mode=None)
        except Exception as inner_e:
            logger.error(LOG_MSGS.MSG_REPLY_ERR.format(user_id=user_id, err=inner_e))
            
    await db.log_request(user_id, user_name, user_input, final_response, current_mode)

    if user_id != ADMIN_ID:
        report = MESSAGES.ADMIN_REPORT.format(
            user_name=html.escape(user_name),
            mode=current_mode,
            has_url='Да' if found_url else 'Нет',
            text=html.escape(user_input),
            response=html.escape(final_response)
        )
        try:
            await bot.send_message(ADMIN_ID, report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send admin report: {e}")

async def main():
    """Boot sequence"""
    global http_session
    
    logger.info(LOG_MSGS.STARTUP)
    await db.init_db()

    states["current_model"] = await db.get_setting("current_model", SETTINGS.MOD_L17)
    
    http_session = aiohttp.ClientSession()
    try:
        await dp.start_polling(bot)
    finally:
        logger.info(LOG_MSGS.SHUTDOWN)
        await http_session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot manually stopped via KeyboardInterrupt.")
        pass