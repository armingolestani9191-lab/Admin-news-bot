import secrets
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = None

from storage import get_value, set_value
from users import ensure_user, get_user, update_user


PLANS = {
    "10": {"days": 10, "price": 20000, "title": "۱۰ روز"},
    "20": {"days": 20, "price": 35000, "title": "۲۰ روز"},
    "30": {"days": 30, "price": 50000, "title": "۳۰ روز (۱ ماه)"},
    "60": {"days": 60, "price": 80000, "title": "۶۰ روز (۲ ماه)"},
}

FREE_DAYS = 3
FREE_MAX_CHANNELS = 1
PAID_MAX_CHANNELS = 3
FREE_ALLOWED_CATEGORIES = ["ورزش", "آب‌وهوا"]
FREE_LOCKED_TIMES = {1, 5}
_DEFAULT_CARD = "6037-9975-1111-2222"
ADMIN_IDS = [595450272]

_STORAGE_NAMESPACE = "subscription"
_LICENSES_KEY = "licenses"
_PAYMENTS_KEY = "payments"
_CARD_KEY = "card"


def today_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN).date()
    return date.today()


def get_card_number():
    data = get_value(_STORAGE_NAMESPACE, _CARD_KEY, {})

    number = ""

    if isinstance(data, dict):
        number = str(data.get("number") or "").strip()
    elif isinstance(data, str):
        number = data.strip()

    return number or _DEFAULT_CARD


def set_card_number(raw):
    text = str(raw or "").strip().replace(" ", "")
    digits = "".join(ch for ch in text if ch.isdigit())

    if len(digits) < 12 or len(digits) > 19:
        return None

    if len(digits) == 16:
        number = (
            f"{digits[0:4]}-"
            f"{digits[4:8]}-"
            f"{digits[8:12]}-"
            f"{digits[12:16]}"
        )
    else:
        number = digits

    set_value(
        _STORAGE_NAMESPACE,
        _CARD_KEY,
        {"number": number},
    )

    return number


CARD_NUMBER = get_card_number()


def load_licenses():
    data = get_value(
        _STORAGE_NAMESPACE,
        _LICENSES_KEY,
        {},
    )

    return data if isinstance(data, dict) else {}


def save_licenses(data):
    set_value(
        _STORAGE_NAMESPACE,
        _LICENSES_KEY,
        data,
    )


def load_payments():
    data = get_value(
        _STORAGE_NAMESPACE,
        _PAYMENTS_KEY,
        {},
    )

    return data if isinstance(data, dict) else {}


def save_payments(data):
    set_value(
        _STORAGE_NAMESPACE,
        _PAYMENTS_KEY,
        data,
    )


def parse_expire(value):
    if not value:
        return None

    text = str(value).strip()[:10]

    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def subscription_info(user_id):
    user = get_user(user_id) or {}
    sub = (
        user.get("subscription")
        if isinstance(user.get("subscription"), dict)
        else {}
    )

    kind = str(sub.get("type") or "none").strip().lower() or "none"

    expire = parse_expire(
        sub.get("expire")
        or sub.get("expires")
        or sub.get("expire_date")
    )

    total = int(sub.get("total_days") or 0)

    remaining = 0
    active = False
    today = today_tehran()

    if expire and expire >= today:
        remaining = (expire - today).days

        if remaining <= 0:
            remaining = 1

        active = True

    elif expire and expire < today:
        kind = "expired"
        remaining = 0
        active = False

    if kind in (None, "none", "", "expired") and not active:
        kind = "none" if not expire else "expired"

    if not active:
        kind = "none" if kind == "none" else "expired"
        remaining = 0

    label = "ندارد"

    if active and kind == "free":
        label = "رایگان"
    elif active:
        label = "پولی"

    return {
        "type": kind if active else (
            "none" if kind == "none" else "expired"
        ),
        "active": active,
        "expire": expire.isoformat() if expire else None,
        "remaining": remaining,
        "total": total or remaining,
        "label": label,
    }


def has_subscription(user_id):
    return bool(subscription_info(user_id)["active"])


def is_free_user(user_id):
    info = subscription_info(user_id)

    return info["active"] and info["type"] == "free"


def max_channels_for(user_id):
    if not has_subscription(user_id):
        return 0

    return (
        FREE_MAX_CHANNELS
        if is_free_user(user_id)
        else PAID_MAX_CHANNELS
    )


def activate_subscription(user_id, kind, days, extra=None):
    ensure_user(user_id)

    expire = today_tehran() + timedelta(
        days=max(1, int(days))
    )

    payload = {
        "subscription": {
            "type": kind,
            "expire": expire.isoformat(),
            "total_days": int(days),
        }
    }

    if isinstance(extra, dict):
        payload.update(extra)

    return bool(update_user(user_id, payload))


def claim_free_subscription(
    user_id,
    first_name="",
    username=None,
):
    ensure_user(user_id, first_name, username)

    info = subscription_info(user_id)
    user = get_user(user_id, force=True) or {}

    if info["active"]:
        return False, "already"

    if user.get("free_claimed"):
        return False, "claimed"

    ok = activate_subscription(
        user_id,
        "free",
        FREE_DAYS,
        {"free_claimed": True},
    )

    if not ok:
        return False, "save"

    return True, FREE_DAYS


def clear_subscription(user_id):
    ensure_user(user_id)

    return bool(
        update_user(
            user_id,
            {
                "subscription": {
                    "type": None,
                    "expire": None,
                    "total_days": 0,
                }
            },
        )
    )


def create_license(days):
    days = int(days)

    code = (
        f"ANB-{days}-"
        f"{secrets.token_hex(4).upper()}"
    )

    licenses = load_licenses()

    licenses[code] = {
        "days": days,
        "used": False,
        "used_by": None,
    }

    save_licenses(licenses)

    return code


def redeem_license(user_id, code):
    code = (code or "").strip().upper()

    licenses = load_licenses()
    item = licenses.get(code)

    if not item:
        return False, "کد لایسنس غلط است."

    if item.get("used"):
        return False, "این کد قبلاً استفاده شده است."

    days = int(item.get("days") or 0)

    if days <= 0:
        return False, "کد نامعتبر است."

    activate_subscription(
        user_id,
        "paid",
        days,
    )

    item["used"] = True
    item["used_by"] = str(user_id)

    licenses[code] = item

    save_licenses(licenses)

    return True, days
