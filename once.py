_SEEN = {}


def once(obj, scope=""):
    key = f"{scope}:{id(obj)}"
    if key in _SEEN:
        return False
    _SEEN[key] = True
    if len(_SEEN) > 400:
        keep = key
        _SEEN.clear()
        _SEEN[keep] = True
    return True
