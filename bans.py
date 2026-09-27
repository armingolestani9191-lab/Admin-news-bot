import json
import os

from storage import users_path


_CACHE = set()
_MTIME = None


def _path():
    return os.path.join(os.path.dirname(users_path()) or "data", "banned.json")


def _load():
    global _CACHE, _MTIME
    path = _path()
    try:
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    except OSError:
        mtime = 0
    if _MTIME is not None and mtime == _MTIME:
        return _CACHE
    ids = set()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                raw = json.load(file)
            if isinstance(raw, list):
                for item in raw:
                    try:
                        ids.add(int(item))
                    except Exception:
                        continue
        except Exception:
            ids = set(_CACHE)
    _CACHE = ids
    _MTIME = mtime
    return _CACHE


def _save(ids):
    global _CACHE, _MTIME
    path = _path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    clean = sorted(set(int(item) for item in ids))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(clean, file, ensure_ascii=False)
    os.replace(tmp, path)
    _CACHE = set(clean)
    try:
        _MTIME = os.path.getmtime(path)
    except OSError:
        _MTIME = 0


def is_banned(user_id):
    try:
        return int(user_id) in _load()
    except Exception:
        return False


def ban_user(user_id):
    user_id = int(user_id)
    ids = set(_load())
    if user_id in ids:
        return False
    ids.add(user_id)
    _save(ids)
    return True


def unban_user(user_id):
    user_id = int(user_id)
    ids = set(_load())
    if user_id not in ids:
        return False
    ids.discard(user_id)
    _save(ids)
    return True
