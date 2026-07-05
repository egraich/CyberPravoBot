import aiosqlite
import re
import os
from datetime import datetime
from typing import Optional

class Database:
    """
    Asynchronous database controller for SQLite using aiosqlite.
    Handles logging of user interactions and user settings.
    """
    def __init__(self, db_path: str = "/data/cyber_shield.db") -> None:
        """
        Initializes the database controller and ensures the destination directory exists.
        
        :param db_path: The absolute filesystem path to the SQLite database file.
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self) -> None:
        """Initializes database tables asynchronously."""
        async with aiosqlite.connect(self.db_path) as conn:
            # TABLE 1: Logs (History of all system scans)
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
            
            # TABLE 2: User Settings
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    mode TEXT DEFAULT 'general'
                )
            ''')
            await conn.commit()
            
            # TABLE 3: Server/System Settings (Key-Value Store)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            await conn.commit()

    # --- USER SETTINGS MANAGEMENT ---

    async def set_user_mode(self, user_id: int, mode: str) -> None:
        """Saves or updates the active analysis mode for a specific user."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                INSERT INTO user_settings (user_id, mode) 
                VALUES (?, ?) 
                ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
            ''', (user_id, mode))
            await conn.commit()

    async def get_user_mode(self, user_id: int) -> str:
        """Retrieves the analysis mode for a user. Defaults to 'general'."""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("SELECT mode FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else "general"

    # --- LOGGING SYSTEM ---

    def extract_risk_score(self, bot_text: str) -> Optional[int]:
        """Extracts the integer risk score percentage from the AI's response."""
        try:
            first_line = bot_text.strip().split('\n')[0]
            match = re.search(r'(\d+)(?=%)', first_line)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    async def log_request(self, user_id: int, username: str, user_text: str, bot_verdict: str, mode: str) -> None:
        """Logs the complete user request and AI verdict into the database."""
        score = self.extract_risk_score(bot_verdict)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                INSERT INTO logs (user_id, username, user_text, bot_verdict, risk_score, mode, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, user_text, bot_verdict, score, mode, datetime.now()))
            await conn.commit()

    # --- SYSTEM SETTINGS MANAGEMENT ---

    async def set_setting(self, key: str, value: str) -> None:
        """
        Saves or updates a global configuration setting in the persistent Key-Value store.
        
        :param key: Unique identifier for the configuration parameter.
        :param value: The configuration value to store (will be cast to string).
        """
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                'INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)',
                (key, str(value))
            )
            await conn.commit()
            
    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """
        Retrieves a global configuration setting from the Key-Value stor.
        
        :param key: Unique identifier for the configuration parameter.
        :param default: Fallback value to return if the key does not exist.
        :return: The stored string value or the default value fallback.
        """
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute('SELECT value FROM system_settings WHERE key = ?', (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default