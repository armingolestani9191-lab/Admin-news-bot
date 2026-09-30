from datetime import datetime, timedelta, timezone

TEHRAN_OFFSET = timezone(timedelta(hours=3, minutes=30))
try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = TEHRAN_OFFSET

_FA_TO_EN = {}
for _i in range(10):
    _FA_TO_EN[chr(0x06F0 + _i)] = str(_i)
    _FA_TO_EN[chr(0x0660 + _i)] = str(_i)

PRESETS = [
    ("07:00", "23:00"),
    ("08:00", "23:00"),
    ("09:00", "00:00"),
    ("09:00", "22:00"),
    ("10:00", "22:00"),
    ("13:00", "00:00"),
    ("22:00", "07:00"),
    ("23:00", "08:00"),
    ("00:00", "09:00"),
    ("20:00", "08:00"),
]


def _now_tehran():
    try:
        return datetime.now(TEHRAN)
    except Exception:
        return datetime.now(timezone.utc).astimezone(TEHRAN_OFFSET)


def _normalize_digits(text):
    out = []
    for char in str(text or ""):
        out.append(_FA_TO_EN.get(char, char))
    return "".join(out)


def parse_hhmm(text):
    raw = _normalize_digits(text).strip()
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    if not parts[0].isdigit() or not parts[1].isdigit():
        return None
    if len(parts[1]) != 2:
        return None
    hour = int(parts[0])
    minute = int(parts[1])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def to_minutes(text):
    parsed = parse_hhmm(text)
    if not parsed:
        return None
    hour, minute = parsed.split(":")
    return int(hour) * 60 + int(minute)


def format_range(start, end):
    if not start or not end:
        return "۲۴ ساعته"
    return f"{start} تا {end}"


def schedule_of(channel):
    if not isinstance(channel, dict):
        return "", ""
    start = parse_hhmm(channel.get("active_start") or "")
    end = parse_hhmm(channel.get("active_end") or "")
    if not start or not end or start == end:
        return "", ""
    return start, end


def is_24h(channel):
    start, end = schedule_of(channel)
    return not start


def is_channel_open(channel, now=None):
    start, end = schedule_of(channel)
    if not start:
        return True
    current = now or _now_tehran()
    now_min = current.hour * 60 + current.minute
    start_min = to_minutes(start)
    end_min = to_minutes(end)
    if start_min is None or end_min is None:
        return True
    if start_min < end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min


def parse_custom_range(text):
    raw = _normalize_digits(text or "").strip()
    raw = " ".join(raw.split())
    if "تا" not in raw:
        return None, "بدون متن اضافه باشد.\nمثال درست: ۱۳:۰۰ تا ۰۰:۰۰"
    left, right = raw.split("تا", 1)
    start = parse_hhmm(left)
    end = parse_hhmm(right)
    extra_left = left.replace(":", "").replace(" ", "")
    extra_right = right.replace(":", "").replace(" ", "")
    if not start or not end or not extra_left.isdigit() or not extra_right.isdigit():
        return None, "بدون متن اضافه باشد.\nمثال درست: ۱۳:۰۰ تا ۰۰:۰۰"
    if start == end:
        return None, "ساعت شروع و پایان نباید یکی باشد."
    return (start, end), None


def news_after_wake(channel, published):
    if is_24h(channel):
        return True
    wake_at = float(channel.get("quiet_wake_at") or 0)
    if wake_at <= 0:
        return True
    try:
        published = float(published or 0)
    except (TypeError, ValueError):
        return False
    return published >= wake_at
