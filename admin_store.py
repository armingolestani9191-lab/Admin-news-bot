import json
import os

import requests

from config import BOT_TOKEN, USERS_FILE, FORCE_JOIN_CHANNELS
from subscription import ADMIN_IDS

try:
    from storage import users_path
    DATA_DIR = os.path.dirname(users_path()) or os.path.dirname(USERS_FILE) or "data"
except Exception:
    DATA_DIR = os.path.dirname(USERS_FILE) or "data"

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
JOIN_FILE = os.path.join(DATA_DIR, "force_join.json")
OWNER_ID = int(ADMIN_IDS[0]) if ADMIN_IDS else 0


def _load(path, default):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def extra_admin_ids():
    raw = _load(ADMINS_FILE, [])
    ids = []
    for item in raw:
        try:
            ids.append(int(item))
        except Exception:
            continue
    return ids


def all_admin_ids():
    ids = []
    for item in list(ADMIN_IDS) + extra_admin_ids():
        try:
            value = int(item)
        except Exception:
            continue
        if value not in ids:
            ids.append(value)
    return ids


def is_admin(user_id):
    try:
        return int(user_id) in set(all_admin_ids())
    except Exception:
        return False


def add_admin(user_id):
    user_id = int(user_id)
    if user_id in all_admin_ids():
        return False
    ids = extra_admin_ids()
    ids.append(user_id)
    _save(ADMINS_FILE, ids)
    return True


def remove_admin(user_id):
    user_id = int(user_id)
    if user_id == OWNER_ID:
        return False
    ids = [item for item in extra_admin_ids() if item != user_id]
    _save(ADMINS_FILE, ids)
    return True


def _join_keys(item):
    keys = set()
    if not isinstance(item, dict):
        item = {"username": item, "id": item}
    for value in (item.get("username"), item.get("id")):
        if value is None or value == "":
            continue
        text = str(value).strip()
        keys.add(text.lower())
        keys.add(text.lower().lstrip("@"))
        if not text.startswith("@") and not text.lstrip("-").isdigit():
            keys.add("@" + text.lower())
    return keys


def load_join_channels():
    if not os.path.exists(JOIN_FILE):
        data = list(FORCE_JOIN_CHANNELS or [])
        _save(JOIN_FILE, data)
    else:
        data = _load(JOIN_FILE, [])
        if not isinstance(data, list):
            data = []
    clean = []
    seen = set()
    for item in data or []:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or item.get("id") or "").strip()
        if not username:
            continue
        if not username.startswith("@") and not str(item.get("id", "")).lstrip("-").isdigit():
            username = "@" + username
        row = {
            "id": item.get("id") or username,
            "username": username,
        }
        marker = tuple(sorted(_join_keys(row)))
        if marker in seen:
            continue
        seen.add(marker)
        clean.append(row)
    return clean[:3]


def save_join_channels(items):
    clean = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or item.get("id") or "").strip()
        if not username:
            continue
        clean.append({
            "id": item.get("id") or username,
            "username": username,
        })
    _save(JOIN_FILE, clean[:3])


def add_join_channel(channel):
    if not channel:
        return False, "کانال پیدا نشد."
    items = load_join_channels()
    new_keys = _join_keys(channel)
    if any(not _join_keys(item).isdisjoint(new_keys) for item in items):
        return False, "این کانال قبلاً هست."
    if len(items) >= 3:
        return False, "سقف ۳ کانال پر است."
    items.append({
        "id": channel.get("id") or channel.get("username"),
        "username": channel.get("username") or channel.get("id"),
    })
    save_join_channels(items)
    return True, "اضافه شد."


def remove_join_channel(text):
    raw = (text or "").strip()
    if not raw:
        return False
    items = load_join_channels()
    raw_keys = _join_keys({"username": raw, "id": raw})
    keep = [item for item in items if _join_keys(item).isdisjoint(raw_keys)]
    if len(keep) == len(items):
        return False
    save_join_channels(keep)
    return True


def resolve_channel(username):
    username = (username or "").strip()
    if not username:
        return None
    if not username.startswith("@") and not username.lstrip("-").isdigit():
        username = "@" + username
    try:
        response = requests.post(
            f"{BASE_URL}/getChat",
            json={"chat_id": username},
            timeout=10,
        )
        payload = response.json()
        if payload.get("ok"):
            result = payload.get("result") or {}
            uname = result.get("username")
            return {
                "id": result.get("id") or username,
                "username": ("@" + uname) if uname else username,
            }
    except Exception:
        pass
    if username.startswith("@"):
        return {"id": username, "username": username}
    return None
