import sqlite3
import time

DB_PATH = "/data/bot.db"

def save_comment(user_id: int, channel_id: int, text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO comments (channel_id, user_id, message, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (channel_id, user_id, text, int(time.time())))
    conn.commit()
    conn.close()

def remember_post(owner_id: int, channel_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO sent_comments (channel_id, message_id)
        VALUES (?, ?)
    ''', (channel_id, message_id))
    conn.commit()
    conn.close()

def post_comment(channel_id: int, text: str, reply_to: int = None):
    # اینجا کد واقعی ارسال کامنت رو بنویس (مثلاً با bale API)
    # مثال ساده:
    # bot.send_message(channel_id, f"💬 {text}", reply_to_message_id=reply_to)
    pass
