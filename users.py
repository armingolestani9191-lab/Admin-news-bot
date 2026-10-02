# ==========================
# AutoNewsBot Users
# SQLite Storage Edition
# ==========================

from datetime import datetime

from config import DEFAULT_SEND_INTERVAL
from storage import (
    get_user as _db_get_user,
    load_users as _db_load_users,
    save_user as _db_save_user,
    save_users as _db_save_users,
)


# ==========================
# Persian / Arabic Digits
# ==========================

_FA_DIGITS = {}

for _i in range(10):
    _FA_DIGITS[0x06F0 + _i] = 48 + _i
    _FA_DIGITS[0x0660 + _i] = 48 + _i


# ==========================
# Internal Helpers
# ==========================

def _blank_user(first_name="", username=None):
    """
    Create a completely new user structure.

    The structure is intentionally kept compatible
    with the previous JSON implementation.
    """

    return {
        "first_name": first_name or "",
        "username": username,
        "join_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "wallet": 0,
        "channels": [],
        "subscription": {
            "type": None,
            "expire": None,
            "total_days": 0,
        },
        "free_claimed": False,
        "invited_by": None,
        "invite_count": 0,
        "is_admin": False,
    }


def _sub_expire(user):
    """
    Get subscription expiration date for compatibility
    with the previous user-merging logic.
    """

    if not isinstance(user, dict):
        return ""

    subscription = user.get("subscription")

    if not isinstance(subscription, dict):
        return ""

    return str(
        subscription.get("expire")
        or subscription.get("expires")
        or subscription.get("expire_date")
        or ""
    )[:10]


def _prefer_user(left, right):
    """
    Merge two user dictionaries while preserving
    the most useful data.

    Kept for compatibility and for possible future
    migrations/imports.
    """

    if not isinstance(left, dict):
        return right if isinstance(right, dict) else {}

    if not isinstance(right, dict):
        return left

    chosen = dict(left)

    for key, value in right.items():

        if key in (
            "subscription",
            "channels",
            "free_claimed",
        ):
            continue

        if value not in (
            None,
            "",
            [],
            {},
        ) or key not in chosen:
            chosen[key] = value

    left_exp = _sub_expire(left)
    right_exp = _sub_expire(right)

    if right_exp > left_exp:
        chosen["subscription"] = right.get("subscription")

    elif left_exp:
        chosen["subscription"] = left.get("subscription")

    elif isinstance(
        right.get("subscription"),
        dict,
    ):
        chosen["subscription"] = right.get(
            "subscription"
        )

    elif isinstance(
        left.get("subscription"),
        dict,
    ):
        chosen["subscription"] = left.get(
            "subscription"
        )

    left_channels = (
        left.get("channels")
        if isinstance(
            left.get("channels"),
            list,
        )
        else []
    )

    right_channels = (
        right.get("channels")
        if isinstance(
            right.get("channels"),
            list,
        )
        else []
    )

    if len(right_channels) > len(left_channels):
        chosen["channels"] = right_channels
    else:
        chosen["channels"] = left_channels

    chosen["free_claimed"] = bool(
        left.get("free_claimed")
        or right.get("free_claimed")
    )

    return chosen


# ==========================
# Users Database API
# ==========================

def load_users(force=False):
    """
    Load all users from SQLite.

    `force` is kept for compatibility with the
    previous implementation.
    """

    return _db_load_users()


def save_users(users):
    """
    Save users to SQLite.
    """

    return _db_save_users(users)


def ensure_user(
    user_id,
    first_name="",
    username=None,
):
    """
    Make sure a user exists.
    """

    user_id = str(user_id)

    current = _db_get_user(user_id)

    if not isinstance(current, dict):

        current = _blank_user(
            first_name,
            username,
        )

        _db_save_user(
            user_id,
            current,
        )

        return current

    changed = False

    if (
        first_name
        and current.get("first_name") != first_name
    ):
        current["first_name"] = first_name
        changed = True

    if (
        username
        and current.get("username") != username
    ):
        current["username"] = username
        changed = True

    if changed:
        _db_save_user(
            user_id,
            current,
        )

    return current


def user_exists(user_id):
    """
    Check whether a user exists.
    """

    return _db_get_user(str(user_id)) is not None


def add_user(
    user_id,
    first_name,
    username=None,
):
    """
    Add a user if it does not already exist.
    """

    current = _db_get_user(
        str(user_id)
    )

    if isinstance(current, dict):

        same_name = (
            not first_name
            or current.get("first_name") == first_name
        )

        same_user = (
            not username
            or current.get("username") == username
        )

        if same_name and same_user:
            return

    ensure_user(
        user_id,
        first_name,
        username,
    )


def get_user(
    user_id,
    force=False,
):
    """
    Get one user.

    `force` is kept for compatibility.
    """

    return _db_get_user(
        str(user_id)
    )


def search_users(query):
    """
    Search for a user by:
    - ID
    - username
    - first name
    """

    raw = str(
        query or ""
    ).strip().lstrip("@").translate(
        _FA_DIGITS
    )

    if not raw:
        return None

    users = load_users(
        force=True
    )

    # Exact user ID
    if raw in users:
        return raw

    # Numeric user ID
    if raw.isdigit():

        number = str(
            int(raw)
        )

        if number in users:
            return number

        if raw in users:
            return raw

    needle = raw.lower()

    exact = []
    partial = []

    for user_id, user in users.items():

        if not isinstance(
            user,
            dict,
        ):
            continue

        username = str(
            user.get("username")
            or ""
        ).lstrip("@").lower()

        first_name = str(
            user.get("first_name")
            or ""
        ).lower()

        user_id_text = str(
            user_id
        )

        if (
            username == needle
            or first_name == needle
            or user_id_text == raw
        ):
            exact.append(
                user_id_text
            )

        elif (
            needle
            and (
                needle in username
                or needle in first_name
                or needle in user_id_text
            )
        ):
            partial.append(
                user_id_text
            )

    if exact:
        return exact[0]

    if partial:
        return partial[0]

    return None


def update_user(
    user_id,
    data,
):
    """
    Update fields of a user.
    """

    user_id = str(user_id)

    current = _db_get_user(
        user_id
    )

    if not isinstance(current, dict):
        current = _blank_user()

    if not isinstance(data, dict):
        return False

    incoming_subscription = data.get(
        "subscription"
    )

    current_subscription = current.get(
        "subscription"
    )

    current.update(data)

    if isinstance(
        incoming_subscription,
        dict,
    ):
        current["subscription"] = (
            incoming_subscription
        )

    elif (
        isinstance(
            current_subscription,
            dict,
        )
        and not incoming_subscription
    ):
        current["subscription"] = (
            current_subscription
        )

    return _db_save_user(
        user_id,
        current,
    )


# ==========================
# Channel Helpers
# ==========================

def _patch_channel(
    user_id,
    channel_id,
    updates,
):
    """
    Update one channel belonging to a user.

    This function is intentionally kept public because
    other modules in the project use it directly.
    """

    if not isinstance(
        updates,
        dict,
    ):
        return False

    user_id = str(user_id)

    user = _db_get_user(
        user_id
    )

    if not isinstance(user, dict):
        user = _blank_user()

    target = str(
        channel_id or ""
    ).lower()

    channels = user.setdefault(
        "channels",
        [],
    )

    for channel in channels:

        if not isinstance(
            channel,
            dict,
        ):
            continue

        current_id = str(
            channel.get("id")
            or ""
        ).lower()

        if current_id == target:

            channel.update(
                updates
            )

            return _db_save_user(
                user_id,
                user,
            )

    return False


def add_channel(
    user_id,
    channel,
    max_channels=3,
):
    """
    Add a channel to a user.
    """

    from channel_utils import normalize_channel_id

    channel = (
        normalize_channel_id(channel)
        or channel
    )

    user_id = str(user_id)

    user = _db_get_user(
        user_id
    )

    if not isinstance(user, dict):
        user = _blank_user()

    channels = user.setdefault(
        "channels",
        [],
    )

    try:
        max_channels = int(
            max_channels or 0
        )
    except Exception:
        max_channels = 0

    if len(channels) >= max_channels:
        return False

    target = str(
        channel
    ).lower()

    for item in channels:

        if not isinstance(
            item,
            dict,
        ):
            continue

        if (
            str(
                item.get("id")
                or ""
            ).lower()
            == target
        ):
            return False

    # Keep existing subscription behavior.
    from subscription import (
        is_free_user,
        FREE_ALLOWED_CATEGORIES,
    )

    if is_free_user(user_id):
        default_categories = list(
            FREE_ALLOWED_CATEGORIES
        )
    else:
        default_categories = [
            "همه"
        ]

    channels.append(
        {
            "id": channel,
            "status": "active",
            "send_image": True,
            "show_emoji": True,
            "footer_text": "",
            "interval": int(
                DEFAULT_SEND_INTERVAL
                or 1
            ),
            "last_send": 0,
            "categories": default_categories,
            "comment_on": False,
            "comment_text": "",
        }
    )

    _db_save_user(
        user_id,
        user,
    )

    return True


def delete_channel(
    user_id,
    channel_id,
):
    """
    Delete a channel from a user.
    """

    user_id = str(user_id)

    user = _db_get_user(
        user_id
    )

    if not isinstance(user, dict):
        return False

    channels = user.get(
        "channels",
        [],
    )

    target = str(
        channel_id or ""
    ).lower()

    keep = []

    for item in channels:

        if not isinstance(
            item,
            dict,
        ):
            continue

        item_id = str(
            item.get("id")
            or ""
        ).lower()

        if item_id != target:
            keep.append(item)

    if len(keep) == len(channels):
        return False

    user["channels"] = keep

    _db_save_user(
        user_id,
        user,
    )

    return True


def set_channel_status(
    user_id,
    channel_id,
    status,
):
    return _patch_channel(
        user_id,
        channel_id,
        {
            "status": status,
        },
    )


def _toggle_flag(
    user_id,
    channel_id,
    key,
    default=True,
):
    """
    Toggle a boolean channel setting.
    """

    user_id = str(user_id)

    user = _db_get_user(
        user_id
    )

    if not isinstance(user, dict):
        return None

    target = str(
        channel_id or ""
    ).lower()

    for channel in user.get(
        "channels",
        [],
    ):

        if not isinstance(
            channel,
            dict,
        ):
            continue

        current_id = str(
            channel.get("id")
            or ""
        ).lower()

        if current_id == target:

            channel[key] = not channel.get(
                key,
                default,
            )

            _db_save_user(
                user_id,
                user,
            )

            return channel[key]

    return None


def toggle_channel_image(
    user_id,
    channel_id,
):
    return _toggle_flag(
        user_id,
        channel_id,
        "send_image",
        True,
    )


def toggle_channel_emoji(
    user_id,
    channel_id,
):
    return _toggle_flag(
        user_id,
        channel_id,
        "show_emoji",
        True,
    )


def update_footer_text(
    user_id,
    channel_id,
    text,
):
    return _patch_channel(
        user_id,
        channel_id,
        {
            "footer_text": text,
        },
    )


def update_categories(
    user_id,
    channel_id,
    categories,
):
    if not categories:
        categories = [
            "همه"
        ]

    return _patch_channel(
        user_id,
        channel_id,
        {
            "categories": categories,
        },
    )


def update_send_time(
    user_id,
    channel_id,
    interval,
):
    try:
        interval = int(interval)
    except Exception:
        return False

    interval = max(
        1,
        min(
            interval,
            180,
        ),
    )

    return _patch_channel(
        user_id,
        channel_id,
        {
            "interval": interval,
        },
    )


def update_last_send(
    user_id,
    channel_id,
    last_send,
):
    return _patch_channel(
        user_id,
        channel_id,
        {
            "last_send": last_send,
        },
    )


def update_quiet_hours(
    user_id,
    channel_id,
    start="",
    end="",
):
    payload = {
        "active_start": start or "",
        "active_end": end or "",
    }

    if not start or not end:
        payload["quiet_wake_at"] = 0

    return _patch_channel(
        user_id,
        channel_id,
        payload,
    )


def mark_quiet_wake(
    user_id,
    channel_id,
    wake_at,
):
    return _patch_channel(
        user_id,
        channel_id,
        {
            "quiet_wake_at": float(
                wake_at or 0
            ),
            "last_send": 0,
            "price_at_طلا و ارز": 0,
            "price_at_ارز دیجیتال": 0,
        },
    )
