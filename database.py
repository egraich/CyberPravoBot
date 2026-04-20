import sqlite3
import re
import os
from datetime import datetime

class Database:
    def __init__(self, db_path="/data/cyber_shield.db"):
        self.db_path = db_path
        
        # Убеждаемся, что папка data существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            # Добавлена колонка username [cite: 2, 3]
            conn.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    user_text TEXT,
                    bot_verdict TEXT,
                    risk_score INTEGER,
                    timestamp DATETIME
                )
            ''')

    def extract_risk_score(self, bot_text):
        try:
            # Парсим число из первой строки ответа ИИ [cite: 4, 5]
            first_line = bot_text.strip().split('\n')[0]
            match = re.search(r'^1\.\s*(\d+)%', first_line)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def log_request(self, user_id, username, user_text, bot_verdict):
        score = self.extract_risk_score(bot_verdict)
        with sqlite3.connect(self.db_path) as conn:
            # Теперь записываем 6 колонок вместо 5 [cite: 6]
            conn.execute('''
                INSERT INTO logs (user_id, username, user_text, bot_verdict, risk_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, user_text, bot_verdict, score, datetime.now()))