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
    """
    Return additional admin IDs stored in SQLite.

    This replaces admins.json.
    """

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
    """
    Return all admin IDs.

    ADMIN_IDS from subscription.py remain the
    permanent/default admins, while additional
    admins are stored in SQLite.
    """

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
    """
    Check whether a user is an admin.
    """

    try:
        return int(user_id) in set(
            all_admin_ids()
        )
    except Exception:
        return False


def add_admin(user_id):
    """
    Add an additional admin.
    """

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
    """
    Remove an additional admin.

    The owner cannot be removed.
    """

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


def _join_keys(item):
    """
    Generate comparable keys for a force-join
    channel.
    """

    keys = set()

    if not isinstance(item, dict):
        item = {
            "username": item,
            "id": item,
        }

    values = [
        item.get("username"),
        item.get("id"),
        item,
    ]

    for value in values:

        text = _norm(value)

        if not text:
            continue

        if (
            text.startswith("{")
            or text.startswith("<")
        ):
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

        if (
            low.startswith("@")
            and len(low) > 1
        ):
            keys.add(
                low[1:]
            )

    return {
        key
        for key in keys
        if key
    }


def _normalize_row(item):
    """
    Normalize a force-join channel entry.

    Keeps the same output structure as the old
    JSON implementation.
    """

    if not isinstance(item, dict):

        text = _norm(item)

        if not text:
            return None

        if (
            not text.startswith("@")
            and not text.lstrip("-").isdigit()
        ):
            text = "@" + text

        return {
            "id": text,
            "username": text,
        }

    username = _norm(
        item.get("username")
        or item.get("id")
    )

    channel_id = item.get("id")

    if (
        channel_id is None
        or _norm(channel_id) == ""
    ):
        channel_id = username

    if not username:
        username = _norm(
            channel_id
        )

    if not username:
        return None

    if (
        not username.startswith("@")
        and not str(username).lstrip("-").isdigit()
    ):
        username = "@" + username

    return {
        "id": channel_id,
        "username": username,
    }


def _clean_list(data):
    """
    Normalize, remove duplicates and keep the
    original maximum of 3 force-join channels.
    """

    clean = []
    seen = set()

    for item in data or []:

        row = _normalize_row(item)

        if not row:
            continue

        marker = tuple(
            sorted(
                _join_keys(row)
            )
        )

        if not marker:
            continue

        if marker in seen:
            continue

        seen.add(marker)

        clean.append(row)

    return clean[:3]


# ==========================
# Force Join Storage
# ==========================

def save_join_channels(items):
    """
    Save force-join channels into SQLite.
    """

    clean = _clean_list(items)

    set_value(
        JOIN_NAMESPACE,
        JOIN_KEY,
        clean,
    )

    return clean


def load_join_channels():
    """
    Load force-join channels from SQLite.

    If nothing has ever been stored, the original
    FORCE_JOIN_CHANNELS configuration is used as
    the initial data.
    """

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
    """
    Add a force-join channel.
    """

    row = _normalize_row(
        channel
    )

    if not row:
        return False, "کانال پیدا نشد."

    items = load_join_channels()

    new_keys = _join_keys(
        row
    )

    if any(
        not _join_keys(item).isdisjoint(
            new_keys
        )
        for item in items
    ):
        return False, "این کانال قبلاً هست."

    if len(items) >= 3:
        return False, "سقف ۳ کانال پر است."

    items.append(row)

    save_join_channels(
        items
    )

    return True, "اضافه شد."


def remove_join_channel(text):
    """
    Remove a force-join channel by username/id.
    """

    if isinstance(text, dict):

        raw_keys = _join_keys(
            text
        )

    else:

        raw = _norm(text)

        if not raw:
            return False

        raw_keys = _join_keys(
            {
                "username": raw,
                "id": raw,
            }
        )

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
    """
    Remove a force-join channel by its list index.
    """

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
    Resolve a Bale channel using getChat.

    This logic is unchanged from the previous
    implementation.
    """

    username = _norm(
        username
    )

    if not username:
        return None

    if (
        username.startswith("https://")
        or username.startswith("http://")
    ):
        username = (
            username
            .rstrip("/")
            .split("/")[-1]
        )

    if (
        not username.startswith("@")
        and not username.lstrip("-").isdigit()
    ):
        username = "@" + username

    try:

        response = requests.post(
            f"{BASE_URL}/getChat",
            json={
                "chat_id": username,
            },
            timeout=10,
        )

        payload = response.json()

        if payload.get("ok"):

            result = (
                payload.get("result")
                or {}
            )

            uname = result.get(
                "username"
            )

            return {
                "id": (
                    result.get("id")
                    if result.get("id")
                    is not None
                    else username
                ),

                "username": (
                    "@" + uname
                    if uname
                    else username
                ),
            }

    except Exception:
        pass

    return {
        "id": username,
        "username": username,
        }
