import time

from channel_checker import get_chat_member
from admin_store import load_join_channels


# =========================================================
# Force Join Cache
# =========================================================

_JOINED = {}

# وقتی کاربر واقعاً عضو تشخیص داده شد، مدت کوتاهی کش می‌شود.
# وقتی عضو نباشد، کش خیلی کوتاه است تا بعد از Join سریع دوباره چک شود.
JOINED_CACHE_SECONDS = 30
NOT_JOINED_CACHE_SECONDS = 3


# =========================================================
# Channels
# =========================================================

def get_force_join_channels():
    """
    Return current force-join channels from SQLite.
    """
    try:
        channels = load_join_channels()
    except Exception:
        return []

    if not isinstance(channels, list):
        return []

    clean = []

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        channel_id = channel.get("id")
        username = channel.get("username")

        if not channel_id and not username:
            continue

        clean.append({
            "id": channel_id,
            "username": username,
        })

    return clean


def is_force_join_enabled():
    """
    Force join is enabled only when at least one
    valid channel exists.
    """
    return bool(get_force_join_channels())


# =========================================================
# Cache
# =========================================================

def clear_join_cache(user_id=None):
    """
    Clear membership cache.

    If user_id is None, clear cache for everybody.
    """
    if user_id is None:
        _JOINED.clear()
        return

    _JOINED.pop(str(user_id), None)


def _get_cached(user_id):
    """
    Return cached membership result if it is still valid.
    """
    key = str(user_id)
    item = _JOINED.get(key)

    if not item:
        return None

    expires_at, result = item

    if expires_at <= time.time():
        _JOINED.pop(key, None)
        return None

    return bool(result)


def _set_cache(user_id, result):
    """
    Save membership result with different TTLs.
    """
    key = str(user_id)

    ttl = (
        JOINED_CACHE_SECONDS
        if result
        else NOT_JOINED_CACHE_SECONDS
    )

    _JOINED[key] = (
        time.time() + ttl,
        bool(result),
    )


def _cleanup_cache():
    """
    Remove expired cache entries.
    """
    now = time.time()

    if len(_JOINED) <= 400:
        return

    for key, item in list(_JOINED.items()):
        try:
            expires_at = item[0]
        except Exception:
            _JOINED.pop(key, None)
            continue

        if expires_at <= now:
            _JOINED.pop(key, None)


# =========================================================
# Membership Check
# =========================================================

def _channel_target(channel):
    """
    Return the best target for getChatMember.

    Prefer the numeric channel ID when available.
    Otherwise use username.
    """
    if not isinstance(channel, dict):
        return None

    channel_id = channel.get("id")
    username = channel.get("username")

    if channel_id is not None:
        text = str(channel_id).strip()

        if text:
            return channel_id

    if username:
        text = str(username).strip()

        if text:
            if not text.startswith("@"):
                text = "@" + text

            return text

    return None


def _is_member_status(status):
    """
    Bale membership statuses which mean the user
    currently belongs to the channel.
    """
    if not status:
        return False

    status = str(status).strip().lower()

    return status in {
        "creator",
        "administrator",
        "member",
        "restricted",
    }


def is_user_joined(user_id, force=False):
    """
    Check whether the user has joined ALL force-join channels.

    force=True:
        Always performs a fresh API check.

    force=False:
        Uses a very short cache.
    """

    try:
        user_id = int(user_id)
    except Exception:
        return False

    channels = get_force_join_channels()

    # No force-join channels = no restriction.
    if not channels:
        return True

    # /start and "عضو شدم" can request a fresh check.
    if not force:
        cached = _get_cached(user_id)

        if cached is not None:
            return cached

    # -----------------------------------------------------
    # Check every required channel
    # -----------------------------------------------------

    for channel in channels:
        target = _channel_target(channel)

        # A broken channel entry must NEVER disable
        # force join.
        if not target:
            _set_cache(user_id, False)
            _cleanup_cache()
            return False

        try:
            status = get_chat_member(
                target,
                user_id,
            )
        except Exception:
            status = None

        # API failure / unknown status:
        # fail closed so the user cannot bypass force join.
        if not _is_member_status(status):
            _set_cache(user_id, False)
            _cleanup_cache()
            return False

    # User is a member of every required channel.
    _set_cache(user_id, True)
    _cleanup_cache()

    return True


# =========================================================
# Force Recheck
# =========================================================

def force_check_user(user_id):
    """
    Always perform a fresh force-join check.

    This is intended for:
    - /start
    - "✅ عضو شدم"
    """
    clear_join_cache(user_id)
    return is_user_joined(
        user_id,
        force=True,
    )
