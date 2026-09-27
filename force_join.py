import time

from channel_checker import get_chat_member
from admin_store import load_join_channels


_JOINED = {}


def is_force_join_enabled():
    return bool(load_join_channels())


def get_force_join_channels():
    return load_join_channels()


def is_user_joined(user_id):
    channels = load_join_channels()
    if not channels:
        return True
    now = time.time()
    key = str(user_id)
    cached = _JOINED.get(key)
    if cached and cached[0] > now:
        return cached[1]
    ok_all = True
    for channel in channels:
        ok = False
        for target in (channel.get("id"), channel.get("username")):
            if not target:
                continue
            status = get_chat_member(target, user_id)
            if status in ("creator", "administrator", "member"):
                ok = True
                break
        if not ok:
            ok_all = False
            break
    _JOINED[key] = (now + (45 if ok_all else 8), ok_all)
    if len(_JOINED) > 400:
        cutoff = now
        for item in list(_JOINED):
            if _JOINED[item][0] <= cutoff:
                _JOINED.pop(item, None)
    return ok_all
