from storage import get_value, set_value, delete_value


_NAMESPACE = "bans"


def _key(user_id):
    return str(int(user_id))


def is_banned(user_id):
    try:
        return bool(get_value(_NAMESPACE, _key(user_id), False))
    except Exception:
        return False


def ban_user(user_id):
    user_id = int(user_id)

    if is_banned(user_id):
        return False

    set_value(_NAMESPACE, _key(user_id), True)
    return True


def unban_user(user_id):
    user_id = int(user_id)

    if not is_banned(user_id):
        return False

    delete_value(_NAMESPACE, _key(user_id))
    return True
