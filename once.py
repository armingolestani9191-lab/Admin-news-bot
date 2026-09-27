import time


_SEEN = {}


def _stable_key(obj, scope=""):
    query_id = (
        getattr(obj, "id", None)
        or getattr(obj, "callback_id", None)
        or getattr(obj, "query_id", None)
        or getattr(obj, "message_id", None)
    )
    data = getattr(obj, "data", None) or getattr(obj, "content", None) or ""
    user = getattr(getattr(obj, "from_user", None), "id", "")
    if query_id:
        return f"{scope}:{user}:{query_id}:{data}"
    return f"{scope}:{user}:{id(obj)}:{data}"


def once(obj, scope=""):
    key = _stable_key(obj, scope)
    now = time.time()
    last = _SEEN.get(key, 0)
    if now - last < 1.0:
        return False
    _SEEN[key] = now
    if len(_SEEN) > 400:
        cutoff = now - 8
        for item, stamp in list(_SEEN.items()):
            if stamp < cutoff:
                _SEEN.pop(item, None)
    return True
