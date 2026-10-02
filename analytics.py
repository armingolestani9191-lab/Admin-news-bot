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
    return {"members": {}, "messages": {}}


def _load():
    data = get_value(_STATS_NAMESPACE, _STATS_KEY, None)

    if isinstance(data, dict):
        data.setdefault("members", {})
        data.setdefault("messages", {})
        return data

    return _default_data()


def _save(data):
    set_value(_STATS_NAMESPACE, _STATS_KEY, data)


def get_members_count(channel_id):
    try:
        response = requests.post(
            f"{BASE_URL}/getChatMembersCount",
            json={"chat_id": channel_id},
            timeout=10,
        )
        payload = response.json()
        if payload.get("ok"):
            return int(payload.get("result") or 0)
    except Exception:
        pass

    try:
        response = requests.post(
            f"{BASE_URL}/getChat",
            json={"chat_id": channel_id},
            timeout=10,
        )
        payload = response.json()
        result = payload.get("result") or {}

        for key in ("members_count", "member_count"):
            if result.get(key) is not None:
                return int(result[key])
    except Exception:
        pass

    return 0


def snapshot_members(channel_id):
    count = get_members_count(channel_id)

    if count <= 0:
        return 0

    data = _load()
    items = data["members"].setdefault(str(channel_id), [])
    now = time.time()

    if (
        items
        and now - float(items[-1].get("ts") or 0) < 60
        and items[-1].get("count") == count
    ):
        return count

    items.append({"ts": now, "count": count})
    data["members"][str(channel_id)] = items[-4000:]

    _save(data)

    return count


def record_message(channel_id):
    key = now_tehran().strftime("%Y-%m-%d-%H")

    data = _load()
    channel = data["messages"].setdefault(str(channel_id), {})

    channel[key] = int(channel.get(key) or 0) + 1

    if len(channel) > 900:
        for old in sorted(channel.keys())[:-800]:
            channel.pop(old, None)

    _save(data)


def _count_at_or_before(items, ts):
    best = None

    for item in items:
        if float(item.get("ts") or 0) <= ts:
            best = int(item.get("count") or 0)

    return best


def build_report(channel_id):
    now = now_tehran()
    midnight = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    current = snapshot_members(channel_id)

    data = _load()
    members = data["members"].get(str(channel_id), [])
    messages = data["messages"].get(str(channel_id), {})

    start_today = _count_at_or_before(
        members,
        midnight.timestamp(),
    )

    start_7 = _count_at_or_before(
        members,
        (midnight - timedelta(days=7)).timestamp(),
    )

    start_30 = _count_at_or_before(
        members,
        (midnight - timedelta(days=30)).timestamp(),
    )

    users_today = (
        max(0, current - start_today)
        if start_today is not None
        else 0
    )

    users_7 = (
        max(0, current - start_7)
        if start_7 is not None
        else users_today
    )

    users_30 = (
        max(0, current - start_30)
        if start_30 is not None
        else users_7
    )

    hours = list(range(now.hour + 1))
    day = now.strftime("%Y-%m-%d")

    hourly = [
        int(messages.get(f"{day}-{hour:02d}") or 0)
        for hour in hours
    ]

    total_today = sum(hourly)

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
