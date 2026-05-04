import sqlite3
import re
import os
from datetime import datetime

class Database:
    def __init__(self, db_path="/data/cyber_shield.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._create_tables()

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            # ТАБЛИЦА 1: Логи (История всех проверок)
            conn.execute('''
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
            
            # ТАБЛИЦА 2: Настройки
            # user_id тут UNIQUE, чтобы настройки не дублировались
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    mode TEXT DEFAULT 'general'
                )
            ''')

    # --- РАБОТА С НАСТРОЙКАМИ ЮЗЕРА ---

    def set_user_mode(self, user_id, mode) -> None:
        """Сохраняем или обновляем режим юзера."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_settings (user_id, mode) 
                VALUES (?, ?) 
                ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
            ''', (user_id, mode))

    def get_user_mode(self, user_id) -> str:
        """Достаем режим. Если юзера нет — выдаем 'general'."""
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT mode FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
            return res[0] if res else "general"

    # --- ЛОГИРОВАНИЕ ---

    def extract_risk_score(self, bot_text):
        try:
            first_line = bot_text.strip().split('\n')[0]
            match = re.search(r'(\d+)(?=%)', first_line)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def log_request(self, user_id, username, user_text, bot_verdict, mode):
        """Записываем всё, включая режим, в котором проводился анализ."""
        score = self.extract_risk_score(bot_verdict)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO logs (user_id, username, user_text, bot_verdict, risk_score, mode, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, user_text, bot_verdict, score, mode, datetime.now()))