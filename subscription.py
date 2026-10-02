# ==========================
# AutoNewsBot Subscription
# SQLite Storage Edition
# ==========================

from datetime import datetime, timedelta
import secrets
import string

from storage import (
    get_setting,
    set_setting,
)


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
# Settings Keys
# ==========================

CARD_KEY = "subscription_card_number"

SUPPORT_KEY = "support_username"


# ==========================
# Internal Helpers
# ==========================

def _setting(key, default=None):
    try:
        value = get_setting(key)

        if value is None:
            return default

        return value

    except Exception:
        return default


def _save_setting(key, value):
    try:
        return set_setting(
            key,
            value,
        )
    except Exception:
        return False


def _plan_key(plan_id):
    return f"subscription_plan_{str(plan_id)}"


def _load_plan(plan_id):
    default = DEFAULT_PLANS.get(
        str(plan_id)
    )

    if not default:
        return None

    saved = _setting(
        _plan_key(plan_id),
        None,
    )

    if not isinstance(saved, dict):
        return dict(default)

    plan = dict(default)

    for key in (
        "title",
        "days",
        "price",
    ):
        if key in saved:
            plan[key] = saved[key]

    try:
        plan["days"] = int(
            plan["days"]
        )
    except Exception:
        plan["days"] = default["days"]

    try:
        plan["price"] = int(
            plan["price"]
        )
    except Exception:
        plan["price"] = default["price"]

    return plan


def _load_plans():
    plans = {}

    for plan_id in DEFAULT_PLANS:
        plan = _load_plan(plan_id)

        if plan:
            plans[plan_id] = plan

    return plans


# ==========================
# Public Plans
# ==========================

class _Plans(dict):
    """
    Dynamic dictionary.

    This keeps compatibility with existing code:

        PLANS.get("30")

    while still loading the latest prices
    from SQLite.
    """

    def get(self, key, default=None):
        plans = _load_plans()

        return plans.get(
            str(key),
            default,
        )

    def __getitem__(self, key):
        plans = _load_plans()

        return plans[str(key)]

    def __contains__(self, key):
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


# ==========================
# Plan Management
# ==========================

def get_plan(plan_id):
    """
    Get the latest version of a subscription plan.
    """

    return _load_plan(
        str(plan_id)
    )


def get_all_plans():
    """
    Return all subscription plans.
    """

    return _load_plans()


def set_plan_price(
    plan_id,
    price,
):
    """
    Change the price of a subscription plan.

    The new price is stored in SQLite.
    """

    plan_id = str(plan_id)

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


def reset_plan_price(plan_id):
    """
    Reset a plan price to its default value.
    """

    plan_id = str(plan_id)

    if plan_id not in DEFAULT_PLANS:
        return False

    plan = dict(
        DEFAULT_PLANS[plan_id]
    )

    return _save_setting(
        _plan_key(plan_id),
        plan,
    )


# ==========================
# Support Username
# ==========================

DEFAULT_SUPPORT_USERNAME = "@pv_ahzar04"


def get_support_username():
    """
    Get the current support username.
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


def set_support_username(username):
    """
    Change support username and save it in SQLite.
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
    """

    return str(
        _setting(
            CARD_KEY,
            "",
        )
        or ""
    )


def set_card_number(number):
    """
    Save a new card number.
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

    if len(digits) != 16:
        return None

    _save_setting(
        CARD_KEY,
        digits,
    )

    return digits


# ==========================
# Subscription Helpers
# ==========================

def _parse_date(value):
    if not value:
        return None

    value = str(value)

    formats = (
        "%Y-%m-%d %H:%M:%S",
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

    return None


def subscription_info(user_id):
    """
    Return subscription information for a user.
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

    if not expire_date:
        return {
            "active": False,
            "remaining": 0,
            "total": int(
                subscription.get(
                    "total_days",
                    0,
                )
                or 0
            ),
            "label": "بدون اشتراک",
            "type": subscription.get("type"),
            "expire": expire,
        }

    now = datetime.utcnow()

    remaining_seconds = (
        expire_date - now
    ).total_seconds()

    if remaining_seconds <= 0:
        return {
            "active": False,
            "remaining": 0,
            "total": int(
                subscription.get(
                    "total_days",
                    0,
                )
                or 0
            ),
            "label": "منقضی شده",
            "type": subscription.get("type"),
            "expire": expire,
        }

    remaining = max(
        1,
        int(
            remaining_seconds
            / 86400
        ),
    )

    total = int(
        subscription.get(
            "total_days",
            remaining,
        )
        or remaining
    )

    sub_type = subscription.get(
        "type"
    )

    if sub_type == "free":
        label = "رایگان"
    elif sub_type == "paid":
        label = "پولی"
    else:
        label = str(
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


def activate_subscription(
    user_id,
    subscription_type,
    days,
):
    """
    Activate or extend a subscription.
    """

    from users import get_user, update_user

    user_id = str(
        user_id
    )

    try:
        days = int(days)
    except Exception:
        return False

    if days <= 0:
        return False

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

    now = datetime.utcnow()

    if current["active"] and current.get("expire"):
        current_expire = _parse_date(
            current["expire"]
        )

        if current_expire and current_expire > now:
            start = current_expire
        else:
            start = now
    else:
        start = now

    expire = start + timedelta(
        days=days
    )

    total_days = days

    if current["active"]:
        total_days += int(
            current.get(
                "remaining",
                0,
            )
            or 0
        )

    user["subscription"] = {
        "type": subscription_type,
        "expire": expire.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "total_days": total_days,
    }

    return update_user(
        user_id,
        user,
    )


def clear_subscription(
    user_id,
):
    """
    Remove user's subscription.
    """

    from users import update_user

    return update_user(
        str(user_id),
        {
            "subscription": {
                "type": None,
                "expire": None,
                "total_days": 0,
            }
        },
    )


# ==========================
# Free Subscription
# ==========================

FREE_DAYS = 3

FREE_ALLOWED_CATEGORIES = [
    "ایران",
    "جهان",
]


def is_free_user(user_id):
    info = subscription_info(
        user_id
    )

    return (
        info["active"]
        and info["type"] == "free"
    )


def claim_free_subscription(
    user_id,
):
    from users import get_user, update_user

    user_id = str(
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

    if user.get(
        "free_claimed"
    ):
        return False

    ok = activate_subscription(
        user_id,
        "free",
        FREE_DAYS,
    )

    if not ok:
        return False

    user = get_user(
        user_id
    )

    if not isinstance(
        user,
        dict,
    ):
        return False

    user["free_claimed"] = True

    update_user(
        user_id,
        user,
    )

    return True


# ==========================
# License System
# ==========================

def _random_license(length=12):
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


def _licenses():
    value = _setting(
        "subscription_licenses",
        {},
    )

    if not isinstance(
        value,
        dict,
    ):
        return {}

    return value


def _save_licenses(data):
    return _save_setting(
        "subscription_licenses",
        data,
    )


def create_license(days):
    """
    Create a new license code.
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
        "created_at": datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }

    _save_licenses(
        licenses
    )

    return code


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
        return False, "کد لایسنس را وارد کن."

    licenses = _licenses()

    item = licenses.get(
        code
    )

    if not isinstance(
        item,
        dict,
    ):
        return False, "کد لایسنس معتبر نیست."

    if item.get("used"):
        return False, "این کد قبلاً استفاده شده است."

    days = int(
        item.get(
            "days",
            0,
        )
        or 0
    )

    if days <= 0:
        return False, "این کد اشتباه است."

    if not activate_subscription(
        user_id,
        "paid",
        days,
    ):
        return False, "فعال‌سازی اشتراک انجام نشد."

    item["used"] = True
    item["user_id"] = str(
        user_id
    )
    item["used_at"] = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    licenses[code] = item

    _save_licenses(
        licenses
    )

    return True, days
