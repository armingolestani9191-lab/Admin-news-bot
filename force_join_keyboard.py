from bale import InlineKeyboardMarkup, InlineKeyboardButton

from force_join import get_force_join_channels


def _channel_username(channel):
    if not isinstance(channel, dict):
        return ""

    username = str(
        channel.get("username") or ""
    ).strip()

    if not username:
        return ""

    if username.startswith("@"):
        return username

    return "@" + username


def _channel_url(username):
    username = str(
        username or ""
    ).strip()

    if not username:
        return None

    username = username.lstrip("@")

    if not username:
        return None

    # لینک عمومی کانال بله
    return f"https://ble.ir/{username}"


def force_join_keyboard():
    keyboard = InlineKeyboardMarkup()

    channels = get_force_join_channels()

    for channel in channels:
        username = _channel_username(
            channel
        )

        # کانال بدون username عمومی،
        # لینک قابل استفاده برای کاربر ندارد.
        if not username:
            continue

        url = _channel_url(
            username
        )

        if not url:
            continue

        keyboard.add(
            InlineKeyboardButton(
                f"📢 {username}",
                url=url,
            ),
            row=1,
        )

    # دکمه بررسی مجدد عضویت
    keyboard.add(
        InlineKeyboardButton(
            "✅ عضو شدم",
            callback_data="check_force_join",
        ),
        row=2,
    )

    return keyboard
