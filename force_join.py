import time

from channel_checker import get_chat_member
from admin_store import load_join_channels


# =========================================================
# Cache
# =========================================================

_JOIN_CACHE = {}

# نتیجه مثبت مدت بیشتری کش می‌شود
JOINED_CACHE_SECONDS = 30

# نتیجه منفی خیلی کوتاه کش می‌شود
# تا بعد از Join سریع دوباره بررسی شود
NOT_JOINED_CACHE_SECONDS = 2


# =========================================================
# Channels
# =========================================================

def get_force_join_channels():
    """
    دریافت لیست فعلی کانال‌های جوین اجباری
    از SQLite
    """

    try:
        channels = load_join_channels()
    except Exception:
        return []

    if not isinstance(channels, list):
        return []

    result = []

    for channel in channels:
        if not isinstance(channel, dict):
            continue

        channel_id = channel.get("id")
        username = channel.get("username")

        if not channel_id and not username:
            continue

        result.append({
            "id": channel_id,
            "username": username,
        })

    return result


def is_force_join_enabled():
    """
    اگر حداقل یک کانال جوین اجباری وجود داشته باشد،
    جوین اجباری فعال است.
    """

    return bool(
        get_force_join_channels()
    )


# =========================================================
# Cache Management
# =========================================================

def clear_join_cache(user_id=None):
    """
    پاک کردن کش جوین.

    اگر user_id داده شود فقط کش همان کاربر پاک می‌شود.
    """

    if user_id is None:
        _JOIN_CACHE.clear()
        return

    try:
        user_id = int(user_id)
    except Exception:
        return

    _JOIN_CACHE.pop(
        str(user_id),
        None,
    )


def _get_cache(user_id):
    """
    دریافت نتیجه کش‌شده.
    """

    key = str(user_id)

    item = _JOIN_CACHE.get(key)

    if not item:
        return None

    try:
        expires_at = float(item["expires_at"])
        result = bool(item["result"])
    except Exception:
        _JOIN_CACHE.pop(
            key,
            None,
        )
        return None

    if expires_at <= time.time():
        _JOIN_CACHE.pop(
            key,
            None,
        )
        return None

    return result


def _set_cache(user_id, result):
    """
    ذخیره نتیجه کلی.

    نتیجه False فقط چند ثانیه نگه داشته می‌شود
    تا کاربر بعد از Join سریع دوباره بررسی شود.
    """

    key = str(user_id)

    ttl = (
        JOINED_CACHE_SECONDS
        if result
        else NOT_JOINED_CACHE_SECONDS
    )

    _JOIN_CACHE[key] = {
        "result": bool(result),
        "expires_at": time.time() + ttl,
    }


def _cleanup_cache():
    """
    پاک کردن کش‌های منقضی‌شده.
    """

    if len(_JOIN_CACHE) < 300:
        return

    now = time.time()

    for key, item in list(
        _JOIN_CACHE.items()
    ):
        try:
            if float(
                item.get("expires_at", 0)
            ) <= now:
                _JOIN_CACHE.pop(
                    key,
                    None,
                )
        except Exception:
            _JOIN_CACHE.pop(
                key,
                None,
            )


# =========================================================
# Channel Helpers
# =========================================================

def _channel_target(channel):
    """
    مشخص کردن شناسه‌ای که باید برای
    getChatMember استفاده شود.
    """

    if not isinstance(channel, dict):
        return None

    channel_id = channel.get("id")

    if channel_id is not None:
        value = str(channel_id).strip()

        if value:
            return channel_id

    username = channel.get("username")

    if username:
        value = str(username).strip()

        if value:
            if not value.startswith("@"):
                value = "@" + value

            return value

    return None


def _channel_name(channel):
    """
    نام قابل نمایش کانال.
    """

    if not isinstance(channel, dict):
        return "کانال"

    username = str(
        channel.get("username") or ""
    ).strip()

    if username:
        if not username.startswith("@"):
            username = "@" + username

        return username

    channel_id = channel.get("id")

    if channel_id:
        return str(channel_id)

    return "کانال"


def _is_joined_status(status):
    """
    وضعیت‌هایی که یعنی کاربر عضو کانال است.

    creator / administrator:
        مدیر یا مالک کانال

    member:
        عضو عادی

    restricted:
        در Bale اگر کاربر هنوز در کانال باشد
        و فقط محدود شده باشد، عضو محسوب می‌شود.
    """

    if status is None:
        return False

    status = str(status).strip().lower()

    return status in {
        "creator",
        "administrator",
        "member",
        "restricted",
    }


# =========================================================
# Detailed Check
# =========================================================

def get_missing_channel(user_id, force=False):
    """
    بررسی تک‌تک کانال‌های جوین اجباری.

    خروجی:
        None
            یعنی کاربر در همه کانال‌ها عضو است.

        channel dict
            یعنی کاربر حداقل در یک کانال عضو نیست.

    نکته مهم:
    کانال‌ها یکی‌یکی بررسی می‌شوند.
    پس اگر در کانال اول عضو باشد ولی در کانال دوم
    نباشد، کانال دوم برگردانده می‌شود.
    """

    try:
        user_id = int(user_id)
    except Exception:
        return {
            "username": "کانال نامشخص",
            "id": None,
        }

    channels = get_force_join_channels()

    # هیچ کانالی برای جوین اجباری ثبت نشده
    if not channels:
        return None

    # -----------------------------------------------------
    # کش فقط وقتی استفاده می‌شود که force=False باشد.
    #
    # اما برای تشخیص اینکه دقیقاً کدام کانال باقی مانده،
    # بررسی تازه دقیق‌تر است.
    # -----------------------------------------------------

    if not force:
        cached = _get_cache(user_id)

        if cached is True:
            return None

    # -----------------------------------------------------
    # هر کانال جداگانه بررسی می‌شود
    # -----------------------------------------------------

    for channel in channels:

        target = _channel_target(channel)

        # رکورد خراب نباید باعث دور زدن جوین اجباری شود.
        if not target:
            return channel

        try:
            status = get_chat_member(
                target,
                user_id,
            )
        except Exception:
            status = None

        # -------------------------------------------------
        # اگر API وضعیت را برنگرداند،
        # کاربر را عضو فرض نمی‌کنیم.
        # -------------------------------------------------

        if not _is_joined_status(status):
            return channel

    # -----------------------------------------------------
    # رسیدن به اینجا یعنی در همه کانال‌ها عضو است.
    # -----------------------------------------------------

    return None


# =========================================================
# Main Check
# =========================================================

def is_user_joined(user_id, force=False):
    """
    بررسی اینکه کاربر در ALL کانال‌های اجباری عضو است.

    اگر حتی یک کانال را Join نکرده باشد:
        False

    اگر همه را Join کرده باشد:
        True
    """

    try:
        user_id = int(user_id)
    except Exception:
        return False

    channels = get_force_join_channels()

    # هیچ کانال اجباری وجود ندارد
    if not channels:
        return True

    # -----------------------------------------------------
    # اگر force=True باشد، کش کاملاً نادیده گرفته می‌شود.
    # -----------------------------------------------------

    if not force:
        cached = _get_cache(user_id)

        if cached is not None:
            return cached

    missing = get_missing_channel(
        user_id,
        force=True,
    )

    if missing is None:
        _set_cache(
            user_id,
            True,
        )
        _cleanup_cache()
        return True

    # حداقل یک کانال هنوز Join نشده
    _set_cache(
        user_id,
        False,
    )

    _cleanup_cache()

    return False


# =========================================================
# Fresh Check
# =========================================================

def force_check_user(user_id):
    """
    بررسی کاملاً تازه.

    برای:
    - /start
    - دکمه «عضو شدم»

    استفاده می‌شود.
    """

    clear_join_cache(
        user_id
    )

    return is_user_joined(
        user_id,
        force=True,
    )


# =========================================================
# Missing Channel
# =========================================================

def get_user_missing_channel(user_id):
    """
    برگرداندن کانالی که کاربر هنوز در آن عضو نشده.

    این تابع همیشه بررسی تازه انجام می‌دهد.
    """

    clear_join_cache(
        user_id
    )

    return get_missing_channel(
        user_id,
        force=True,
    )
