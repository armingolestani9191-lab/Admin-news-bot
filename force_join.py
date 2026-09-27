from channel_checker import get_chat_member
from admin_store import load_join_channels


def is_force_join_enabled():
    return bool(load_join_channels())


def get_force_join_channels():
    return load_join_channels()


def is_user_joined(user_id):
    channels = load_join_channels()
    if not channels:
        return True
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
            return False
    return True
