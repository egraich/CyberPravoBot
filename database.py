# Copyright (c) 2026 egraich

import aiosqlite
import re
import os
import logging
from datetime import datetime
from typing import Optional
from config import SETTINGS, LOG_MSGS

logger = logging.getLogger("DB_Manager")

class Database:
    """Async sqlite handler for logs and user configs"""
    
    def __init__(self, db_path: str = SETTINGS.DB_PATH) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    async def init_db(self) -> None:
        """Create tables and set performance pragmas"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("PRAGMA journal_mode=WAL;")
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        user_text TEXT,
                        bot_verdict TEXT,
                        risk_score INTEGER,
                        mode TEXT,
                        timestamp DATETIME
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        mode TEXT DEFAULT 'general'
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                await conn.commit()
                logger.info(LOG_MSGS.DB_INIT_OK.format(path=self.db_path))
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="init_db", err=e))

    async def set_user_mode(self, user_id: int, mode: str) -> None:
        """Upsert user active mode"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('''
                    INSERT INTO user_settings (user_id, mode) 
                    VALUES (?, ?) 
                    ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
                ''', (user_id, mode))
                await conn.commit()
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="set_user_mode", err=e))

    async def get_user_mode(self, user_id: int) -> str:
        """Fetch user mode, fallback to general"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.execute("SELECT mode FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
                    res = await cursor.fetchone()
                    return res[0] if res else "general"
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="get_user_mode", err=e))
            return "general"

    def extract_risk_score(self, bot_text: str) -> Optional[int]:
        """Parse raw AI output for percentage score"""
        try:
            match = re.search(r'(\d+)(?=%)', bot_text.strip().split('\n')[0])
            return int(match.group(1)) if match else None
        except Exception:
            return None

    async def log_request(self, user_id: int, username: str, user_text: str, bot_verdict: str, mode: str) -> None:
        """Write scan results to history"""
        score = self.extract_risk_score(bot_verdict)
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('''
                    INSERT INTO logs (user_id, username, user_text, bot_verdict, risk_score, mode, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, user_text, bot_verdict, score, mode, datetime.now()))
                await conn.commit()
                logger.debug(LOG_MSGS.DB_LOG_SAVED.format(user_id=user_id))
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="log_request", err=e))

    async def set_setting(self, key: str, value: str) -> None:
        """Upsert global KV setting"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    'INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)',
                    (key, str(value))
                )
                await conn.commit()
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="set_setting", err=e))
            
    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Fetch global KV setting"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.execute('SELECT value FROM system_settings WHERE key = ?', (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else default
        except Exception as e:
            logger.error(LOG_MSGS.DB_ERROR.format(action="get_setting", err=e))
            return default