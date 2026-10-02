# ==========================
# AutoNewsBot Admin Store
# SQLite Storage Edition
# ==========================

import requests

from config import BOT_TOKEN, FORCE_JOIN_CHANNELS
from subscription import ADMIN_IDS
from storage import (
    get_value,
    set_value,
)


# ==========================
# Bale API
# ==========================

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

_SESSION = requests.Session()

_SESSION.headers.update({
    "Content-Type": "application/json"
})


# ==========================
# Owner
# ==========================

OWNER_ID = int(ADMIN_IDS[0]) if ADMIN_IDS else 0


# ==========================
# SQLite Namespaces
# ==========================

ADMINS_NAMESPACE = "admin_store"
ADMINS_KEY = "extra_admin_ids"

JOIN_NAMESPACE = "admin_store"
JOIN_KEY = "force_join_channels"


# ==========================
# Admins
# ==========================

def extra_admin_ids():
    raw = get_value(
        ADMINS_NAMESPACE,
        ADMINS_KEY,
        [],
    )

    if not isinstance(raw, list):
        return []

    ids = []

    for item in raw:
        try:
            value = int(item)
        except Exception:
            continue

        if value not in ids:
            ids.append(value)

    return ids


def all_admin_ids():
    ids = []

    for item in list(ADMIN_IDS) + extra_admin_ids():
        try:
            value = int(item)
        except Exception:
            continue

        if value not in ids:
            ids.append(value)

    return ids


def is_admin(user_id):
    try:
        return int(user_id) in set(
            all_admin_ids()
        )
    except Exception:
        return False


def add_admin(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False

    if user_id in all_admin_ids():
        return False

    ids = extra_admin_ids()

    ids.append(user_id)

    set_value(
        ADMINS_NAMESPACE,
        ADMINS_KEY,
        ids,
    )

    return True


def remove_admin(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False

    if user_id == OWNER_ID:
        return False

    ids = [
        item
        for item in extra_admin_ids()
        if item != user_id
    ]

    set_value(
        ADMINS_NAMESPACE,
        ADMINS_KEY,
        ids,
    )

    return True


# ==========================
# Normalization Helpers
# ==========================

def _norm(value):
    if value is None:
        return ""

    return str(value).strip()


def _normalize_username(value):
    value = _norm(value)

    if not value:
        return ""

    if (
        value.startswith("https://")
        or value.startswith("http://")
    ):
        value = (
            value
            .rstrip("/")
            .split("/")[-1]
        )

    if (
        not value.startswith("@")
        and not value.lstrip("-").isdigit()
    ):
        value = "@" + value

    return value


def _join_keys(item):
    keys = set()

    if not isinstance(item, dict):
        item = {
            "username": item,
            "id": item,
        }

    values = [
        item.get("username"),
        item.get("id"),
    ]

    for value in values:
        text = _norm(value)

        if not text:
            continue

        low = text.lower()

        keys.add(low)
        keys.add(
            low.lstrip("@")
        )

        if (
            not low.startswith("@")
            and not low.lstrip("-").isdigit()
        ):
            keys.add(
                "@" + low
            )

    return {
        key
        for key in keys
        if key
    }


def _normalize_row(item):
    """
    تبدیل اطلاعات کانال به ساختار استاندارد.
    """

    if not isinstance(item, dict):
        text = _normalize_username(item)

        if not text:
            return None

        return {
            "id": text,
            "username": text,
        }

    channel_id = item.get("id")
    username = item.get("username")

    channel_id = (
        channel_id
        if channel_id is not None
        else ""
    )

    username = _normalize_username(
        username
    )

    if not username:
        username = _normalize_username(
            channel_id
        )

    if (
        channel_id is None
        or _norm(channel_id) == ""
    ):
        channel_id = username

    if not username and not channel_id:
        return None

    return {
        "id": channel_id,
        "username": username,
    }


def _clean_list(data):
    clean = []
    seen = set()

    for item in data or []:
        row = _normalize_row(item)

        if not row:
            continue

        keys = _join_keys(row)

        if not keys:
            continue

        marker = tuple(
            sorted(keys)
        )

        if marker in seen:
            continue

        seen.add(marker)
        clean.append(row)

    return clean[:3]


# ==========================
# Force Join Storage
# ==========================

def save_join_channels(items):
    clean = _clean_list(items)

    set_value(
        JOIN_NAMESPACE,
        JOIN_KEY,
        clean,
    )

    return clean


def load_join_channels():
    raw = get_value(
        JOIN_NAMESPACE,
        JOIN_KEY,
        None,
    )

    if raw is None:
        seeded = _clean_list(
            list(
                FORCE_JOIN_CHANNELS or []
            )
        )

        return save_join_channels(
            seeded
        )

    return _clean_list(raw)


def add_join_channel(channel):
    row = _normalize_row(channel)

    if not row:
        return False, "⚠️ اطلاعات کانال معتبر نیست."

    items = load_join_channels()

    new_keys = _join_keys(row)

    for item in items:
        if not _join_keys(item).isdisjoint(
            new_keys
        ):
            return False, "⚠️ این کانال قبلاً اضافه شده."

    if len(items) >= 3:
        return False, "⚠️ سقف ۳ کانال پر است."

    items.append(row)

    save_join_channels(
        items
    )

    return True, "کانال با موفقیت اضافه شد."


def remove_join_channel(text):
    if isinstance(text, dict):
        raw_keys = _join_keys(text)
    else:
        raw = _norm(text)

        if not raw:
            return False

        raw_keys = _join_keys({
            "username": raw,
            "id": raw,
        })

    if not raw_keys:
        return False

    items = load_join_channels()

    keep = [
        item
        for item in items
        if _join_keys(item).isdisjoint(
            raw_keys
        )
    ]

    if len(keep) == len(items):
        return False

    save_join_channels(
        keep
    )

    return True


def remove_join_channel_at(index):
    items = load_join_channels()

    try:
        index = int(index)
    except Exception:
        return False

    if (
        index < 0
        or index >= len(items)
    ):
        return False

    items.pop(index)

    save_join_channels(
        items
    )

    return True


# ==========================
# Bale Channel Resolver
# ==========================

def resolve_channel(username):
    """
    کانال را از Bale API پیدا می‌کند.

    اگر کانال واقعاً پیدا نشود:
        None

    دیگر اطلاعات جعلی ذخیره نمی‌شود.
    """

    username = _normalize_username(
        username
    )

    if not username:
        return None

    try:
        response = _SESSION.post(
            f"{BASE_URL}/getChat",
            json={
                "chat_id": username,
            },
            timeout=5,
        )

        if response.status_code != 200:
            return None

        payload = response.json()

        if not isinstance(payload, dict):
            return None

        if not payload.get("ok"):
            return None

        result = (
            payload.get("result")
            or {}
        )

        if not isinstance(result, dict):
            return None

        channel_id = result.get("id")

        if channel_id is None:
            return None

        real_username = result.get(
            "username"
        )

        if real_username:
            real_username = (
                "@"
                + str(real_username).lstrip("@")
            )
        else:
            # اگر کانال یوزرنیم عمومی ندارد،
            # همان ورودی کاربر را نگه می‌داریم.
            real_username = username

        return {
            "id": channel_id,
            "username": real_username,
        }

    except Exception as error:
        print(
            "resolve_channel error:",
            error,
        )
        return None
