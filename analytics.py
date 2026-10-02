import time
from datetime import datetime, timedelta

import requests

from config import BOT_TOKEN
from storage import get_value, set_value


try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = None


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

_STATS_NAMESPACE = "analytics"
_STATS_KEY = "channel_stats"


def now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)

    return datetime.now()


def _default_data():
    return {
        "members": {},
        "messages": {},
    }


def _load():
    data = get_value(
        _STATS_NAMESPACE,
        _STATS_KEY,
        None,
    )

    if isinstance(data, dict):
        data.setdefault(
            "members",
            {},
        )
        data.setdefault(
            "messages",
            {},
        )

        return data

    return _default_data()


def _save(data):
    set_value(
        _STATS_NAMESPACE,
        _STATS_KEY,
        data,
    )


def get_members_count(channel_id):
    try:
        response = requests.post(
            f"{BASE_URL}/getChatMembersCount",
            json={
                "chat_id": channel_id,
            },
            timeout=10,
        )

        payload = response.json()

        if payload.get("ok"):
            return int(
                payload.get("result") or 0
            )

    except Exception:
        pass

    try:
        response = requests.post(
            f"{BASE_URL}/getChat",
            json={
                "chat_id": channel_id,
            },
            timeout=10,
        )

        payload = response.json()
        result = payload.get("result") or {}

        for key in (
            "members_count",
            "member_count",
        ):
            if result.get(key) is not None:
                return int(
                    result[key]
                )

    except Exception:
        pass

    return 0


def snapshot_members(channel_id):
    count = get_members_count(
        channel_id
    )

    if count <= 0:
        return 0

    data = _load()

    items = data[
        "members"
    ].setdefault(
        str(channel_id),
        [],
    )

    now = time.time()

    if (
        items
        and now
        - float(
            items[-1].get("ts") or 0
        )
        < 60
        and items[-1].get("count")
        == count
    ):
        return count

    items.append(
        {
            "ts": now,
            "count": count,
        }
    )

    data["members"][
        str(channel_id)
    ] = items[-4000:]

    _save(data)

    return count


def record_message(channel_id):
    key = now_tehran().strftime(
        "%Y-%m-%d-%H"
    )

    data = _load()

    channel = data[
        "messages"
    ].setdefault(
        str(channel_id),
        {},
    )

    channel[key] = (
        int(
            channel.get(key) or 0
        )
        + 1
    )

    if len(channel) > 900:
        for old in sorted(
            channel.keys()
        )[:-800]:
            channel.pop(
                old,
                None,
            )

    _save(data)


def _count_at_or_before(
    items,
    ts,
):
    best = None
    best_ts = None

    for item in items:
        try:
            item_ts = float(
                item.get("ts") or 0
            )
            item_count = int(
                item.get("count") or 0
            )
        except Exception:
            continue

        if item_ts <= ts:
            if (
                best_ts is None
                or item_ts > best_ts
            ):
                best_ts = item_ts
                best = item_count

    return best


def _count_before_or_after(
    items,
    ts,
):
    """
    اگر snapshot دقیقاً قبل از زمان موردنظر
    وجود نداشت، نزدیک‌ترین snapshot موجود
    را پیدا می‌کند.

    اولویت:
    1. نزدیک‌ترین snapshot قبل از زمان
    2. اگر نبود، نزدیک‌ترین snapshot بعد از زمان
    """

    before = None
    before_ts = None

    after = None
    after_ts = None

    for item in items:
        try:
            item_ts = float(
                item.get("ts") or 0
            )
            item_count = int(
                item.get("count") or 0
            )
        except Exception:
            continue

        if item_ts <= ts:
            if (
                before_ts is None
                or item_ts > before_ts
            ):
                before_ts = item_ts
                before = item_count

        else:
            if (
                after_ts is None
                or item_ts < after_ts
            ):
                after_ts = item_ts
                after = item_count

    if before is not None:
        return before

    return after


def _count_at_start(
    items,
    start_ts,
    current,
):
    """
    مقدار اعضا در ابتدای بازه را پیدا می‌کند.

    اگر تاریخچه کافی وجود داشته باشد:
        اعضای فعلی - اعضای ابتدای بازه

    اگر تاریخچه کافی نباشد:
        صفر برمی‌گرداند تا عدد جعلی تولید نشود.
    """

    if not items:
        return None

    value = _count_before_or_after(
        items,
        start_ts,
    )

    if value is None:
        return None

    return max(
        0,
        current - value,
    )


def build_report(channel_id):
    now = now_tehran()

    midnight = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    current = snapshot_members(
        channel_id
    )

    data = _load()

    members = data[
        "members"
    ].get(
        str(channel_id),
        [],
    )

    messages = data[
        "messages"
    ].get(
        str(channel_id),
        {},
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 👥 آمار اعضا
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    start_today = midnight.timestamp()

    start_7 = (
        midnight
        - timedelta(days=7)
    ).timestamp()

    start_30 = (
        midnight
        - timedelta(days=30)
    ).timestamp()

    users_today = _count_at_start(
        members,
        start_today,
        current,
    )

    users_7 = _count_at_start(
        members,
        start_7,
        current,
    )

    users_30 = _count_at_start(
        members,
        start_30,
        current,
    )

    # اگر تاریخچه کافی برای یک بازه وجود نداشته باشد،
    # عدد صفر نمایش داده می‌شود و به بازه دیگری نسبت داده نمی‌شود.
    if users_today is None:
        users_today = 0

    if users_7 is None:
        users_7 = 0

    if users_30 is None:
        users_30 = 0

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📈 آمار پیام‌های امروز
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    hours = list(
        range(now.hour + 1)
    )

    day = now.strftime(
        "%Y-%m-%d"
    )

    hourly = [
        int(
            messages.get(
                f"{day}-{hour:02d}"
            ) or 0
        )
        for hour in hours
    ]

    total_today = sum(
        hourly
    )

    return {
        "channel_id": channel_id,
        "now": now,
        "midnight": midnight,

        "members": current,

        "users_today": users_today,
        "users_7": users_7,
        "users_30": users_30,

        "hours": hours,
        "hourly": hourly,

        "messages_today": total_today,
    }
