# ==========================
# AutoNewsBot Subscription
# SQLite Storage Edition
# ==========================

from datetime import date, datetime, timedelta
import os
import secrets
import string

from storage import (
    get_value,
    set_value,
)

try:
    from zoneinfo import ZoneInfo

    try:
        TEHRAN = ZoneInfo("Asia/Tehran")
    except Exception:
        TEHRAN = None
except Exception:
    TEHRAN = None


# ==========================
# Admin IDs
# ==========================

try:
    from config import ADMIN_IDS
except Exception:
    ADMIN_IDS = []


# ==========================
# Default Plans
# ==========================

DEFAULT_PLANS = {
    "10": {
        "title": "۱۰ روزه",
        "days": 10,
        "price": 15000,
    },
    "20": {
        "title": "۲۰ روزه",
        "days": 20,
        "price": 25000,
    },
    "30": {
        "title": "۳۰ روزه",
        "days": 30,
        "price": 35000,
    },
    "60": {
        "title": "۶۰ روزه",
        "days": 60,
        "price": 55000,
    },
}


# ==========================
# Subscription Limits
# ==========================

FREE_DAYS = 3

FREE_MAX_CHANNELS = 1

PAID_MAX_CHANNELS = 3

FREE_ALLOWED_CATEGORIES = [
    "ایران",
    "جهان",
]

# Compatibility with older code
FREE_LOCKED_TIMES = {1, 5}


# ==========================
# Storage
# ==========================

SETTINGS_NAMESPACE = "subscription"

CARD_KEY = "subscription_card_number"
OLD_CARD_KEY = "card"

SUPPORT_KEY = "support_username"

PAYMENTS_KEY = "payments"

LICENSES_KEY = "subscription_licenses"
OLD_LICENSES_KEY = "licenses"


# ==========================
# Default Card
# ==========================

_DEFAULT_CARD = os.getenv(
    "CARD_NUMBER",
    "",
)


# ==========================
# Default Support
# ==========================

DEFAULT_SUPPORT_USERNAME = "@pv_ahzar04"


# ==========================
# Date Helpers
# ==========================

def today_tehran():
    """
    Return today's date in Tehran timezone.
    """

    if TEHRAN is not None:
        try:
            return datetime.now(TEHRAN).date()
        except Exception:
            pass

    return date.today()


def _now_datetime():
    """
    Return current datetime.

    Uses Tehran timezone when available.
    """

    if TEHRAN is not None:
        try:
            return datetime.now(TEHRAN).replace(
                tzinfo=None
            )
        except Exception:
            pass

    return datetime.utcnow()


def _parse_date(value):
    """
    Parse both old and new subscription date formats.
    """

    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime(
            value.year,
            value.month,
            value.day,
        )

    value = str(value).strip()

    if not value:
        return None

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            )
        except Exception:
            pass

    # ISO fallback
    try:
        return datetime.fromisoformat(
            value.replace("Z", "")
        )
    except Exception:
        return None


def parse_expire(value):
    """
    Compatibility helper.

    Returns date object.
    """

    parsed = _parse_date(value)

    if parsed is None:
        return None

    return parsed.date()


# ==========================
# Generic Settings
# ==========================

def _setting(
    key,
    default=None,
):
    """
    Read a value from SQLite.
    """

    try:
        value = get_value(
            SETTINGS_NAMESPACE,
            key,
            default,
        )

        if value is None:
            return default

        return value

    except Exception:
        return default


def _save_setting(
    key,
    value,
):
    """
    Save a value into SQLite.
    """

    try:
        return bool(
            set_value(
                SETTINGS_NAMESPACE,
                key,
                value,
            )
        )
    except Exception:
        return False


# ==========================
# Plans
# ==========================

def _plan_key(plan_id):
    return (
        f"subscription_plan_{str(plan_id)}"
    )


def _load_plan(plan_id):
    plan_id = str(plan_id)

    default = DEFAULT_PLANS.get(
        plan_id
    )

    if not default:
        return None

    saved = _setting(
        _plan_key(plan_id),
        None,
    )

    if not isinstance(
        saved,
        dict,
    ):
        return dict(default)

    plan = dict(default)

    if "title" in saved:
        plan["title"] = saved["title"]

    if "days" in saved:
        try:
            plan["days"] = int(
                saved["days"]
            )
        except Exception:
            plan["days"] = default["days"]

    if "price" in saved:
        try:
            plan["price"] = int(
                saved["price"]
            )
        except Exception:
            plan["price"] = default["price"]

    return plan


def _load_plans():
    plans = {}

    for plan_id in DEFAULT_PLANS:
        plan = _load_plan(
            plan_id
        )

        if plan:
            plans[plan_id] = plan

    return plans


class _Plans(dict):
    """
    Dynamic PLANS dictionary.

    Existing code can still use:

        PLANS.get("30")
        PLANS["30"]
        PLANS.items()
    """

    def get(
        self,
        key,
        default=None,
    ):
        plans = _load_plans()

        return plans.get(
            str(key),
            default,
        )

    def __getitem__(
        self,
        key,
    ):
        plans = _load_plans()

        return plans[str(key)]

    def __contains__(
        self,
        key,
    ):
        plans = _load_plans()

        return str(key) in plans

    def items(self):
        return _load_plans().items()

    def keys(self):
        return _load_plans().keys()

    def values(self):
        return _load_plans().values()

    def __iter__(self):
        return iter(
            _load_plans()
        )

    def __len__(self):
        return len(
            _load_plans()
        )


PLANS = _Plans()


def get_plan(plan_id):
    """
    Get one subscription plan.
    """

    return _load_plan(
        str(plan_id)
    )


def get_all_plans():
    """
    Get all subscription plans.
    """

    return _load_plans()


def set_plan_price(
    plan_id,
    price,
):
    """
    Change subscription plan price
    and save it permanently in SQLite.
    """

    plan_id = str(
        plan_id
    )

    if plan_id not in DEFAULT_PLANS:
        return False

    try:
        price = int(price)
    except Exception:
        return False

    if price < 0:
        return False

    plan = _load_plan(
        plan_id
    )

    if not plan:
        return False

    plan["price"] = price

    return _save_setting(
        _plan_key(plan_id),
        plan,
    )


def reset_plan_price(
    plan_id,
):
    """
    Reset plan price to default.
    """

    plan_id = str(
        plan_id
    )

    if plan_id not in DEFAULT_PLANS:
        return False

    return _save_setting(
        _plan_key(plan_id),
        dict(
            DEFAULT_PLANS[plan_id]
        ),
    )


# ==========================
# Support Username
# ==========================

def get_support_username():
    """
    Get current support username.
    """

    value = _setting(
        SUPPORT_KEY,
        DEFAULT_SUPPORT_USERNAME,
    )

    value = str(
        value or ""
    ).strip()

    if not value:
        return DEFAULT_SUPPORT_USERNAME

    if not value.startswith("@"):
        value = "@" + value

    return value


def set_support_username(
    username,
):
    """
    Save support username in SQLite.
    """

    username = str(
        username or ""
    ).strip()

    if not username:
        return False

    username = username.lstrip("@").strip()

    if not username:
        return False

    username = "@" + username

    return _save_setting(
        SUPPORT_KEY,
        username,
    )


# ==========================
# Card Number
# ==========================

def get_card_number():
    """
    Get saved card number.

    Supports both the new SQLite key
    and the old storage key.
    """

    value = _setting(
        CARD_KEY,
        None,
    )

    if value:
        if isinstance(value, dict):
            number = str(
                value.get("number")
                or ""
            ).strip()

            if number:
                return number

        elif isinstance(value, str):
            number = value.strip()

            if number:
                return number

    old_value = _setting(
        OLD_CARD_KEY,
        None,
    )

    if isinstance(
        old_value,
        dict,
    ):
        number = str(
            old_value.get("number")
            or ""
        ).strip()

        if number:
            return number

    elif isinstance(
        old_value,
        str,
    ):
        number = old_value.strip()

        if number:
            return number

    return str(
        _DEFAULT_CARD
        or ""
    ).strip()


def set_card_number(
    number,
):
    """
    Save card number in SQLite.

    Accepts 16 digit cards and also
    keeps compatibility with 12-19 digits.
    """

    number = str(
        number or ""
    ).strip()

    digits = (
        number
        .replace(" ", "")
        .replace("-", "")
    )

    if not digits.isdigit():
        return None

    if len(digits) < 12:
        return None

    if len(digits) > 19:
        return None

    if len(digits) == 16:
        formatted = (
            f"{digits[0:4]}-"
            f"{digits[4:8]}-"
            f"{digits[8:12]}-"
            f"{digits[12:16]}"
        )
    else:
        formatted = digits

    if not _save_setting(
        CARD_KEY,
        formatted,
    ):
        return None

    return formatted


# ==========================
# Payments
# ==========================

def load_payments():
    """
    Load payment requests from SQLite.
    """

    data = _setting(
        PAYMENTS_KEY,
        {},
    )

    if not isinstance(
        data,
        dict,
    ):
        return {}

    return data


def save_payments(
    data,
):
    """
    Save payment requests to SQLite.
    """

    if not isinstance(
        data,
        dict,
    ):
        return False

    return _save_setting(
        PAYMENTS_KEY,
        data,
    )


# ==========================
# Subscription Info
# ==========================

def subscription_info(
    user_id,
):
    """
    Return current subscription information.
    """

    from users import get_user

    user = get_user(
        user_id
    )

    if not isinstance(
        user,
        dict,
    ):
        return {
            "active": False,
            "remaining": 0,
            "total": 0,
            "label": "بدون اشتراک",
            "type": None,
            "expire": None,
        }

    subscription = user.get(
        "subscription"
    )

    if not isinstance(
        subscription,
        dict,
    ):
        return {
            "active": False,
            "remaining": 0,
            "total": 0,
            "label": "بدون اشتراک",
            "type": None,
            "expire": None,
        }

    expire = (
        subscription.get("expire")
        or subscription.get("expires")
        or subscription.get("expire_date")
    )

    expire_date = _parse_date(
        expire
    )

    total_days = 0

    try:
        total_days = int(
            subscription.get(
                "total_days",
                0,
            )
            or 0
        )
    except Exception:
        total_days = 0

    if not expire_date:
        return {
            "active": False,
            "remaining": 0,
            "total": total_days,
            "label": "بدون اشتراک",
            "type": subscription.get(
                "type"
            ),
            "expire": expire,
        }

    now = _now_datetime()

    remaining_seconds = (
        expire_date - now
    ).total_seconds()

    if remaining_seconds <= 0:

        return {
            "active": False,
            "remaining": 0,
            "total": total_days,
            "label": "منقضی شده",
            "type": subscription.get(
                "type"
            ),
            "expire": expire,
        }

    remaining = max(
        1,
        int(
            remaining_seconds / 86400
        ),
    )

    total = (
        total_days
        or remaining
    )

    sub_type = str(
        subscription.get(
            "type"
        )
        or ""
    ).strip().lower()

    if sub_type == "free":
        label = "رایگان"

    elif sub_type == "paid":
        label = "پولی"

    else:
        label = (
            sub_type
            or "اشتراک"
        )

    return {
        "active": True,
        "remaining": remaining,
        "total": total,
        "label": label,
        "type": sub_type,
        "expire": expire,
    }


# ==========================
# Subscription Status
# ==========================

def has_subscription(
    user_id,
):
    """
    Compatibility function used by:
        news_targets.py
        handlers/home.py
    """

    return bool(
        subscription_info(
            user_id
        )["active"]
    )


def is_free_user(
    user_id,
):
    info = subscription_info(
        user_id
    )

    return bool(
        info["active"]
        and info["type"] == "free"
    )


def max_channels_for(
    user_id,
):
    """
    Free users:
        1 channel

    Paid users:
        3 channels
    """

    if not has_subscription(
        user_id
    ):
        return 0

    if is_free_user(
        user_id
    ):
        return FREE_MAX_CHANNELS

    return PAID_MAX_CHANNELS


# ==========================
# Activate Subscription
# ==========================

def activate_subscription(
    user_id,
    subscription_type,
    days,
    extra=None,
):
    """
    Activate or extend a subscription.

    If user already has an active subscription,
    new days are added to the remaining days.
    """

    from users import (
        ensure_user,
        get_user,
        update_user,
    )

    user_id = str(
        user_id
    )

    try:
        days = int(days)
    except Exception:
        return False

    if days <= 0:
        return False

    # Make sure user exists.
    ensure_user(
        user_id
    )

    user = get_user(
        user_id
    )

    if not isinstance(
        user,
        dict,
    ):
        return False

    current = subscription_info(
        user_id
    )

    now = _now_datetime()

    if (
        current["active"]
        and current.get("expire")
    ):
        current_expire = _parse_date(
            current["expire"]
        )

        if (
            current_expire
            and current_expire > now
        ):
            start = current_expire
        else:
            start = now

    else:
        start = now

    expire = (
        start
        + timedelta(days=days)
    )

    # Preserve accumulated remaining days.
    total_days = days

    if current["active"]:
        try:
            total_days += int(
                current.get(
                    "remaining",
                    0,
                )
                or 0
            )
        except Exception:
            pass

    subscription = {
        "type": str(
            subscription_type
        ),
        "expire": expire.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "total_days": total_days,
    }

    user["subscription"] = (
        subscription
    )

    if isinstance(
        extra,
        dict,
    ):
        for key, value in extra.items():
            user[key] = value

    return bool(
        update_user(
            user_id,
            user,
        )
    )


# ==========================
# Clear Subscription
# ==========================

def clear_subscription(
    user_id,
):
    """
    Remove user's subscription.
    """

    from users import (
        ensure_user,
        update_user,
    )

    user_id = str(
        user_id
    )

    ensure_user(
        user_id
    )

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


# ==========================
# Free Subscription
# ==========================

def claim_free_subscription(
    user_id,
    first_name="",
    username=None,
):
    """
    Claim the 3-day free subscription.

    Supports both:
        claim_free_subscription(user_id)

    and:
        claim_free_subscription(
            user_id,
            first_name,
            username,
        )
    """

    from users import (
        ensure_user,
        get_user,
    )

    user_id = str(
        user_id
    )

    ensure_user(
        user_id,
        first_name,
        username,
    )

    info = subscription_info(
        user_id
    )

    user = get_user(
        user_id
    ) or {}

    if info["active"]:
        return False, "already"

    if user.get(
        "free_claimed"
    ):
        return False, "claimed"

    ok = activate_subscription(
        user_id,
        "free",
        FREE_DAYS,
        {
            "free_claimed": True,
        },
    )

    if not ok:
        return False, "save"

    return True, FREE_DAYS


# ==========================
# License Storage
# ==========================

def _licenses():
    """
    Load licenses.

    Reads the new key first and falls back
    to the old key for compatibility.
    """

    data = _setting(
        LICENSES_KEY,
        None,
    )

    if isinstance(
        data,
        dict,
    ):
        return data

    old_data = _setting(
        OLD_LICENSES_KEY,
        {},
    )

    if isinstance(
        old_data,
        dict,
    ):
        return old_data

    return {}


def _save_licenses(
    data,
):
    """
    Save licenses.
    """

    return _save_setting(
        LICENSES_KEY,
        data,
    )


# ==========================
# License Generator
# ==========================

def _random_license(
    length=12,
):
    alphabet = (
        string.ascii_uppercase
        + string.digits
    )

    return "".join(
        secrets.choice(
            alphabet
        )
        for _ in range(length)
    )


def create_license(
    days,
):
    """
    Create a new license.
    """

    try:
        days = int(days)
    except Exception:
        return None

    if days <= 0:
        return None

    licenses = _licenses()

    code = _random_license()

    while code in licenses:
        code = _random_license()

    licenses[code] = {
        "days": days,
        "used": False,
        "user_id": None,
        "used_by": None,
        "created_at": _now_datetime().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }

    if not _save_licenses(
        licenses
    ):
        return None

    return code


# ==========================
# Redeem License
# ==========================

def redeem_license(
    user_id,
    code,
):
    """
    Redeem a license code.
    """

    code = str(
        code or ""
    ).strip().upper()

    if not code:
        return (
            False,
            "کد لایسنس را وارد کن.",
        )

    licenses = _licenses()

    item = licenses.get(
        code
    )

    if not isinstance(
        item,
        dict,
    ):
        return (
            False,
            "کد لایسنس معتبر نیست.",
        )

    if item.get(
        "used"
    ):
        return (
            False,
            "این کد قبلاً استفاده شده است.",
        )

    try:
        days = int(
            item.get(
                "days",
                0,
            )
            or 0
        )
    except Exception:
        days = 0

    if days <= 0:
        return (
            False,
            "این کد اشتباه است.",
        )

    ok = activate_subscription(
        user_id,
        "paid",
        days,
    )

    if not ok:
        return (
            False,
            "فعال‌سازی اشتراک انجام نشد.",
        )

    item["used"] = True
    item["user_id"] = str(
        user_id
    )
    item["used_by"] = str(
        user_id
    )
    item["used_at"] = _now_datetime().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    licenses[code] = item

    if not _save_licenses(
        licenses
    ):
        return (
            False,
            "ذخیره مصرف لایسنس انجام نشد.",
        )

    return True, days
