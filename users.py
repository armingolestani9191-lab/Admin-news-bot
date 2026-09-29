import json
import os
import time
from datetime import datetime

from storage import users_path
from config import DEFAULT_SEND_INTERVAL

_LOCK_PATH = users_path() + ".lock"
_CACHE = {"path": None, "mtime": None, "data": None}
_FA_DIGITS = {}
for _i in range(10):
    _FA_DIGITS[0x06F0 + _i] = 48 + _i
    _FA_DIGITS[0x0660 + _i] = 48 + _i


def _candidate_paths():
    paths = []
    for item in (users_path(), os.path.join("data", "users.json"), os.path.join("Data", "users.json")):
        if item and item not in paths:
            paths.append(item)
    return paths


def _read_users_file(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _sub_expire(user):
    if not isinstance(user, dict):
        return ""
    sub = user.get("subscription")
    if not isinstance(sub, dict):
        return ""
    return str(sub.get("expire") or sub.get("expires") or sub.get("expire_date") or "")[:10]


def _prefer_user(left, right):
    if not isinstance(left, dict):
        return right if isinstance(right, dict) else {}
    if not isinstance(right, dict):
        return left
    chosen = dict(left)
    for key, value in right.items():
        if key in ("subscription", "channels", "free_claimed"):
            continue
        if value not in (None, "", [], {}) or key not in chosen:
            chosen[key] = value
    left_exp = _sub_expire(left)
    right_exp = _sub_expire(right)
    if right_exp > left_exp:
        chosen["subscription"] = right.get("subscription")
    elif left_exp:
        chosen["subscription"] = left.get("subscription")
    elif isinstance(right.get("subscription"), dict):
        chosen["subscription"] = right.get("subscription")
    elif isinstance(left.get("subscription"), dict):
        chosen["subscription"] = left.get("subscription")
    left_channels = left.get("channels") if isinstance(left.get("channels"), list) else []
    right_channels = right.get("channels") if isinstance(right.get("channels"), list) else []
    chosen["channels"] = right_channels if len(right_channels) > len(left_channels) else left_channels
    chosen["free_claimed"] = bool(left.get("free_claimed") or right.get("free_claimed"))
    return chosen


def _acquire_lock():
    os.makedirs(os.path.dirname(users_path()) or ".", exist_ok=True)
    for _ in range(80):
        try:
            fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(_LOCK_PATH) > 8:
                    os.remove(_LOCK_PATH)
                    continue
            except OSError:
                pass
            time.sleep(0.02)
    return False


def _release_lock():
    try:
        os.remove(_LOCK_PATH)
    except OSError:
        pass


def _remember(path, users):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = time.time()
    _CACHE["path"] = path
    _CACHE["mtime"] = mtime
    _CACHE["data"] = users
    return users


def load_users(force=False):
    path = users_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if not force:
        try:
            mtime = os.path.getmtime(path) if os.path.exists(path) else None
        except OSError:
            mtime = None
        if (
            _CACHE["data"] is not None
            and _CACHE["path"] == path
            and _CACHE["mtime"] == mtime
        ):
            return _CACHE["data"]
    merged = {}
    for candidate in _candidate_paths():
        raw = _read_users_file(candidate)
        for user_id, user in raw.items():
            key = str(user_id)
            if key in merged:
                merged[key] = _prefer_user(merged[key], user if isinstance(user, dict) else {})
            else:
                merged[key] = user if isinstance(user, dict) else {}
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(merged, file, ensure_ascii=False, indent=4)
    return _remember(path, merged)


def save_users(users):
    path = users_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    clean = {}
    for user_id, user in (users or {}).items():
        clean[str(user_id)] = user if isinstance(user, dict) else {}
    targets = [path]
    for candidate in _candidate_paths():
        if candidate != path and os.path.exists(os.path.dirname(candidate) or "."):
            if candidate not in targets:
                targets.append(candidate)
    for target in targets:
        folder = os.path.dirname(target)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(clean, file, ensure_ascii=False, indent=4)
        os.replace(tmp, target)
    _remember(path, clean)


def _blank_user(first_name="", username=None):
    return {
        "first_name": first_name or "",
        "username": username,
        "join_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "wallet": 0,
        "channels": [],
        "subscription": {"type": None, "expire": None, "total_days": 0},
        "free_claimed": False,
        "invited_by": None,
        "invite_count": 0,
        "is_admin": False,
    }


def ensure_user(user_id, first_name="", username=None):
    user_id = str(user_id)
    _acquire_lock()
    try:
        users = load_users(force=True)
        if user_id not in users or not isinstance(users.get(user_id), dict):
            users[user_id] = _blank_user(first_name, username)
            save_users(users)
        else:
            changed = False
            current = users[user_id]
            if first_name and current.get("first_name") != first_name:
                current["first_name"] = first_name
                changed = True
            if username and current.get("username") != username:
                current["username"] = username
                changed = True
            if changed:
                save_users(users)
        return users[user_id]
    finally:
        _release_lock()


def _patch_channel(user_id, channel_id, updates):
    _acquire_lock()
    try:
        users = load_users(force=True)
        user_id = str(user_id)
        if user_id not in users:
            users[user_id] = _blank_user()
        target = str(channel_id or "").lower()
        for channel in users[user_id].setdefault("channels", []):
            if str(channel.get("id") or "").lower() == target:
                channel.update(updates)
                save_users(users)
                return True
        return False
    finally:
        _release_lock()


def user_exists(user_id):
    return str(user_id) in load_users()


def add_user(user_id, first_name, username=None):
    ensure_user(user_id, first_name, username)


def get_user(user_id, force=False):
    return load_users(force=force).get(str(user_id))


def search_users(query):
    raw = str(query or "").strip().lstrip("@").translate(_FA_DIGITS)
    if not raw:
        return None
    users = load_users(force=True)
    if raw in users:
        return raw
    if raw.isdigit():
        number = str(int(raw))
        if number in users:
            return number
        if raw in users:
            return raw
    needle = raw.lower()
    exact = []
    partial = []
    for user_id, user in users.items():
        if not isinstance(user, dict):
            continue
        username = str(user.get("username") or "").lstrip("@").lower()
        first_name = str(user.get("first_name") or "").lower()
        if username == needle or first_name == needle or str(user_id) == raw:
            exact.append(str(user_id))
        elif needle and (needle in username or needle in first_name or needle in str(user_id)):
            partial.append(str(user_id))
    if exact:
        return exact[0]
    if partial:
        return partial[0]
    return None


def update_user(user_id, data):
    _acquire_lock()
    try:
        users = load_users(force=True)
        user_id = str(user_id)
        if user_id not in users or not isinstance(users.get(user_id), dict):
            users[user_id] = _blank_user()
        if isinstance(data, dict):
            incoming_sub = data.get("subscription")
            current_sub = users[user_id].get("subscription")
            users[user_id].update(data)
            if isinstance(incoming_sub, dict):
                users[user_id]["subscription"] = incoming_sub
            elif isinstance(current_sub, dict) and not incoming_sub:
                users[user_id]["subscription"] = current_sub
            save_users(users)
            return True
        return False
    finally:
        _release_lock()


def add_channel(user_id, channel, max_channels=3):
    from channel_utils import normalize_channel_id
    channel = normalize_channel_id(channel) or channel
    _acquire_lock()
    try:
        users = load_users(force=True)
        user_id = str(user_id)
        if user_id not in users:
            users[user_id] = _blank_user()
        channels = users[user_id].setdefault("channels", [])
        if len(channels) >= int(max_channels or 0):
            return False
        for item in channels:
            if str(item.get("id") or "").lower() == str(channel).lower():
                return False
        from subscription import is_free_user, FREE_ALLOWED_CATEGORIES
        default_categories = list(FREE_ALLOWED_CATEGORIES) if is_free_user(user_id) else ["همه"]
        channels.append({
            "id": channel,
            "status": "active",
            "send_image": True,
            "show_emoji": True,
            "footer_text": "",
            "interval": int(DEFAULT_SEND_INTERVAL or 1),
            "last_send": 0,
            "categories": default_categories,
            "comment_on": False,
            "comment_text": "",
        })
        save_users(users)
        return True
    finally:
        _release_lock()


def delete_channel(user_id, channel_id):
    _acquire_lock()
    try:
        users = load_users(force=True)
        user_id = str(user_id)
        if user_id not in users:
            return False
        channels = users[user_id].get("channels", [])
        target = str(channel_id or "").lower()
        keep = [item for item in channels if str(item.get("id") or "").lower() != target]
        if len(keep) == len(channels):
            return False
        users[user_id]["channels"] = keep
        save_users(users)
        return True
    finally:
        _release_lock()


def set_channel_status(user_id, channel_id, status):
    return _patch_channel(user_id, channel_id, {"status": status})


def _toggle_flag(user_id, channel_id, key, default=True):
    _acquire_lock()
    try:
        users = load_users(force=True)
        user_id = str(user_id)
        target = str(channel_id or "").lower()
        if user_id not in users:
            return None
        for channel in users[user_id].get("channels", []):
            if str(channel.get("id") or "").lower() == target:
                channel[key] = not channel.get(key, default)
                save_users(users)
                return channel[key]
        return None
    finally:
        _release_lock()


def toggle_channel_image(user_id, channel_id):
    return _toggle_flag(user_id, channel_id, "send_image", True)


def toggle_channel_emoji(user_id, channel_id):
    return _toggle_flag(user_id, channel_id, "show_emoji", True)


def update_footer_text(user_id, channel_id, text):
    return _patch_channel(user_id, channel_id, {"footer_text": text})


def update_categories(user_id, channel_id, categories):
    if not categories:
        categories = ["همه"]
    return _patch_channel(user_id, channel_id, {"categories": categories})


def update_send_time(user_id, channel_id, interval):
    try:
        interval = int(interval)
    except Exception:
        return False
    interval = max(1, min(interval, 180))
    return _patch_channel(user_id, channel_id, {"interval": interval})


def update_last_send(user_id, channel_id, last_send):
    return _patch_channel(user_id, channel_id, {"last_send": last_send})
