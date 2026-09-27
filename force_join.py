import time

from channel_checker import get_chat_member
from admin_store import load_join_channels


_JOINED = {}


def is_force_join_enabled():
    return bool(load_join_channels())


def get_force_join_channels():
    return load_join_channels()


def clear_join_cache(user_id=None):
    if user_id is None:
        _JOINED.clear()
        return
    _JOINED.pop(str(user_id), None)


def is_user_joined(user_id, force=False):
    channels = load_join_channels()
    if not channels:
        return True
    now = time.time()
    key = str(user_id)
    cached = _JOINED.get(key)
    if not force and cached and cached[0] > now:
        return cached[1]
    ok_all = True
    for channel in channels:
        username = channel.get("username")
        channel_id = channel.get("id")
        target = username or channel_id
        if not target:
            continue
        status = get_chat_member(target, user_id)
        if status in ("creator", "administrator", "member"):
            continue
        ok_all = False
        break
    _JOINED[key] = (now + (180 if ok_all else 4), ok_all)
    if len(_JOINED) > 400:
        for item in list(_JOINED):
            if _JOINED[item][0] <= now:
                _JOINED.pop(item, None)
    return ok_all
