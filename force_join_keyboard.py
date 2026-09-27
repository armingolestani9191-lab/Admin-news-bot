from bale import InlineKeyboardMarkup, InlineKeyboardButton

from force_join import get_force_join_channels


def force_join_keyboard():
    keyboard = InlineKeyboardMarkup()
    for channel in get_force_join_channels():
        username = str(channel.get("username") or channel.get("id") or "").strip()
        if not username:
            continue
        slug = username.replace("@", "")
        keyboard.add(
            InlineKeyboardButton(
                f"📢 {username if username.startswith('@') else '@' + username}",
                url=f"https://ble.ir/{slug}",
            ),
            row=1,
        )
    keyboard.add(
        InlineKeyboardButton("✅ عضو شدم", callback_data="check_force_join"),
        row=2,
    )
    return keyboard
