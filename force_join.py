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
        targets = []
        username = channel.get("username")
        channel_id = channel.get("id")
        if username:
            targets.append(username)
        if channel_id and channel_id != username:
            targets.append(channel_id)
        ok = False
        for target in targets:
            status = get_chat_member(target, user_id)
            if status in ("creator", "administrator", "member"):
                ok = True
                break
            if status in ("left", "kicked", "restricted"):
                break
        if not ok:
            ok_all = False
            break
    _JOINED[key] = (now + (180 if ok_all else 6), ok_all)
    if len(_JOINED) > 400:
        for item in list(_JOINED):
            if _JOINED[item][0] <= now:
                _JOINED.pop(item, None)
    return ok_all
