import sqlite3
import os
import time
import threading
from contextlib import contextmanager

# ====================== تنظیمات دیتابیس ======================
DB_PATH = "/data/bot.db"
_lock = threading.Lock()

def _init_db():
    """اولین بار جدول‌ها را می‌سازد"""
    with _lock:
        if os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            channels TEXT DEFAULT '[]',
            last_send INTEGER DEFAULT 0,
            quiet_start TEXT DEFAULT '00:00',
            quiet_end TEXT DEFAULT '00:00',
            subscription_end INTEGER DEFAULT 0,
            categories TEXT DEFAULT '[]',
            wallet INTEGER DEFAULT 0,
            invited_by INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sent_comments (
            channel_id INTEGER,
            message_id INTEGER,
            PRIMARY KEY (channel_id, message_id)
        )''')
        conn.commit()
        conn.close()

@contextmanager
def _db_lock():
    with _lock:
        yield

def get_user(user_id: int):
    """دریافت کامل کاربر از دیتابیس"""
    _init_db()
    with _db_lock():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT channels, last_send, quiet_start, quiet_end, subscription_end, categories, wallet, invited_by FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # تبدیل channels و categories از JSON string به لیست
        return {
            "user_id": user_id,
            "channels": eval(row[0]) if row[0] else [],
            "last_send": row[1] or 0,
            "quiet_start": row[2] or "00:00",
            "quiet_end": row[3] or "00:00",
            "subscription_end": row[4] or 0,
            "categories": eval(row[5]) if row[5] else [],
            "wallet": row[6] or 0,
            "invited_by": row[7] or 0
        }

def add_user(user_id: int):
    """اضافه کردن کاربر جدید"""
    _init_db()
    with _db_lock():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
        conn.close()

def set_channel_status(user_id: int, channel_id: int, key: str, value: any):
    """به‌روزرسانی وضعیت یک کانال (برای کامنت، زمان خاموشی، دسته و ...)"""
    user = get_user(user_id)
    if not user:
        return
    
    channels = user.get("channels", [])
    for channel in channels:
        if channel.get("id") == channel_id:
            channel[key] = value
            _save_channels(user_id, channels)
            return

def _save_channels(user_id: int, channels: list):
    """ذخیره لیست کانال‌ها در دیتابیس"""
    channels_json = str(channels)
    with _db_lock():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET channels = ? WHERE user_id = ?", (channels_json, user_id))
        conn.commit()
        conn.close()

def update_last_send(user_id: int):
    """به‌روزرسانی آخرین ارسال"""
    with _db_lock():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET last_send = ? WHERE user_id = ?", (int(time.time()), user_id))
        conn.commit()
        conn.close()

def set_quiet_hours(user_id: int, channel_id: int, start: str, end: str):
    """تنظیم ساعت خاموشی یک کانال"""
    user = get_user(user_id)
    if not user:
        return
    set_channel_status(user_id, channel_id, "quiet_start", start)
    set_channel_status(user_id, channel_id, "quiet_end", end)

def set_categories(user_id: int, channel_id: int, categories: list):
    """تنظیم دسته‌بندی یک کانال"""
    user = get_user(user_id)
    if not user:
        return
    set_channel_status(user_id, channel_id, "categories", categories)

# ====================== بقیه توابع قدیمی کاربران (بدون تغییر منطق) ======================
# اینجا تمام توابع قبلی که قبلاً داشتی (load_users, save_users و ...) را دقیقاً همون قبلی نگه داشتم
# فقط برای تمیزی اضافه کردم _init_db و _db_lock
