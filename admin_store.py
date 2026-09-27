import json
import os
import time

import requests

from config import BOT_TOKEN, USERS_FILE, FORCE_JOIN_CHANNELS
from subscription import ADMIN_IDS

try:
    from storage import users_path
except Exception:
    users_path = None


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
OWNER_ID = int(ADMIN_IDS[0]) if ADMIN_IDS else 0
_JOIN_CACHE = {"mtime": None, "items": None}


def _data_dirs():
    dirs = []
    try:
        if users_path:
            folder = os.path.dirname(users_path())
            if folder:
                dirs.append(folder)
    except Exception:
        pass
    parent = os.path.dirname(USERS_FILE)
    if parent:
        dirs.append(parent)
    dirs.extend(["data", "Data"])
    clean = []
    for item in dirs:
        if item and item not in clean:
            clean.append(item)
    return clean or ["data"]


def _file_in_dirs(name):
    return [os.path.join(folder, name) for folder in _data_dirs()]


ADMINS_FILE = _file_in_dirs("admins.json")[0]
JOIN_FILE = _file_in_dirs("force_join.json")[0]
_ADMIN_CACHE = {"mtime": None, "ids": None}


def _load(path, default):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _save(path, data):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
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
    global _ADMIN_CACHE
    try:
        mtime = os.path.getmtime(ADMINS_FILE) if os.path.exists(ADMINS_FILE) else 0
    except OSError:
        mtime = 0
    cached = _ADMIN_CACHE.get("ids")
    if cached is not None and _ADMIN_CACHE.get("mtime") == mtime:
        return list(cached)
    ids = []
    for item in list(ADMIN_IDS) + extra_admin_ids():
        try:
            value = int(item)
        except Exception:
            continue
        if value not in ids:
            ids.append(value)
    _ADMIN_CACHE = {"mtime": mtime, "ids": list(ids)}
    return ids


def is_admin(user_id):
    try:
        return int(user_id) in set(all_admin_ids())
    except Exception:
        return False


def add_admin(user_id):
    global _ADMIN_CACHE
    user_id = int(user_id)
    if user_id in all_admin_ids():
        return False
    ids = extra_admin_ids()
    ids.append(user_id)
    _save(ADMINS_FILE, ids)
    _ADMIN_CACHE = {"mtime": None, "ids": None}
    return True


def remove_admin(user_id):
    global _ADMIN_CACHE
    user_id = int(user_id)
    if user_id == OWNER_ID:
        return False
    ids = [item for item in extra_admin_ids() if item != user_id]
    _save(ADMINS_FILE, ids)
    _ADMIN_CACHE = {"mtime": None, "ids": None}
    return True


def _norm(value):
    if value is None:
        return ""
    return str(value).strip()


def _join_keys(item):
    keys = set()
    if not isinstance(item, dict):
        item = {"username": item, "id": item}
    values = [item.get("username"), item.get("id"), item]
    for value in values:
        text = _norm(value)
        if not text or text.startswith("{") or text.startswith("<"):
            continue
        low = text.lower()
        keys.add(low)
        keys.add(low.lstrip("@"))
        if not low.startswith("@") and not low.lstrip("-").isdigit():
            keys.add("@" + low)
        if low.startswith("@") and len(low) > 1:
            keys.add(low[1:])
    return {key for key in keys if key}


def _normalize_row(item):
    if not isinstance(item, dict):
        text = _norm(item)
        if not text:
            return None
        if not text.startswith("@") and not text.lstrip("-").isdigit():
            text = "@" + text
        return {"id": text, "username": text}
    username = _norm(item.get("username") or item.get("id"))
    channel_id = item.get("id")
    if channel_id is None or _norm(channel_id) == "":
        channel_id = username
    if not username:
        username = _norm(channel_id)
    if not username:
        return None
    if not username.startswith("@") and not str(username).lstrip("-").isdigit():
        username = "@" + username
    return {"id": channel_id, "username": username}


def _clean_list(data):
    clean = []
    seen = set()
    for item in data or []:
        row = _normalize_row(item)
        if not row:
            continue
        marker = tuple(sorted(_join_keys(row)))
        if not marker or marker in seen:
            continue
        seen.add(marker)
        clean.append(row)
    return clean[:3]


def _newest_join_path():
    found = []
    for path in _file_in_dirs("force_join.json"):
        if os.path.exists(path):
            try:
                found.append((os.path.getmtime(path), path))
            except OSError:
                found.append((0, path))
    if not found:
        return None
    found.sort(reverse=True)
    return found[0][1]


def save_join_channels(items):
    global _JOIN_CACHE
    clean = _clean_list(items)
    for path in _file_in_dirs("force_join.json"):
        _save(path, clean)
    _JOIN_CACHE = {"mtime": time.time(), "items": list(clean)}
    return clean


def load_join_channels():
    global _JOIN_CACHE
    path = _newest_join_path()
    if not path:
        seeded = _clean_list(list(FORCE_JOIN_CHANNELS or []))
        return save_join_channels(seeded)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if _JOIN_CACHE.get("items") is not None and _JOIN_CACHE.get("mtime") == mtime:
        return list(_JOIN_CACHE["items"])
    items = _clean_list(_load(path, []))
    _JOIN_CACHE = {"mtime": mtime, "items": list(items)}
    return items


def add_join_channel(channel):
    row = _normalize_row(channel)
    if not row:
        return False, "کانال پیدا نشد."
    items = load_join_channels()
    new_keys = _join_keys(row)
    if any(not _join_keys(item).isdisjoint(new_keys) for item in items):
        return False, "این کانال قبلاً هست."
    if len(items) >= 3:
        return False, "سقف ۳ کانال پر است."
    items.append(row)
    save_join_channels(items)
    return True, "اضافه شد."


def remove_join_channel(text):
    if isinstance(text, dict):
        raw_keys = _join_keys(text)
    else:
        raw = _norm(text)
        if not raw:
            return False
        raw_keys = _join_keys({"username": raw, "id": raw})
    if not raw_keys:
        return False
    items = load_join_channels()
    keep = [item for item in items if _join_keys(item).isdisjoint(raw_keys)]
    if len(keep) == len(items):
        return False
    save_join_channels(keep)
    return True


def remove_join_channel_at(index):
    items = load_join_channels()
    try:
        index = int(index)
    except Exception:
        return False
    if index < 0 or index >= len(items):
        return False
    items.pop(index)
    save_join_channels(items)
    return True


def resolve_channel(username):
    username = _norm(username)
    if not username:
        return None
    if username.startswith("https://") or username.startswith("http://"):
        username = username.rstrip("/").split("/")[-1]
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
                "id": result.get("id") if result.get("id") is not None else username,
                "username": ("@" + uname) if uname else username,
            }
    except Exception:
        pass
    return {"id": username, "username": username}
