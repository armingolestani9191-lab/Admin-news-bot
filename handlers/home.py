import time

from bale import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from client import bot
from ui import edit_message
from users import get_user, add_user, set_channel_status
from keyboards import (
    home_inline_menu,
    channel_inline_menu,
    channel_pick_menu,
    plans_menu,
)
from states import set_state, clear_state
from subscription import (
    subscription_info,
    has_subscription,
    max_channels_for,
    claim_free_subscription,
    FREE_DAYS,
)
from force_join import (
    is_force_join_enabled,
    get_user_missing_channel,
)
from force_join_keyboard import force_join_keyboard
from admin_store import is_admin
from quiet_hours import format_range, is_24h, is_channel_open, schedule_of


_START_SEEN = {}


def back_only():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="m_home"), row=1)
    return keyboard


def _need_sub_text():
    return (
        "🔒 هنوز اشتراک فعال نداری\n\n"
        "برای استفاده از ربات اول یکی از این دو راه را برو:\n"
        "🎁 اشتراک رایگان ۳ روزه\n"
        "💳 خرید اشتراک"
    )


def _remember_user(source):
    user = getattr(source, "from_user", None)
    if user is None:
        return
    add_user(
        user.id,
        getattr(user, "first_name", None),
        getattr(user, "username", None),
    )


def _find_channel(channels, channel_id):
    target = str(channel_id or "").strip().lower()

    for item in channels or []:
        if str(item.get("id") or "").strip().lower() == target:
            return item

    return None


def _quiet_block_text(channel):
    start, end = schedule_of(channel or {})
    return (
        f"ولی هنوز تایم فعالیت {channel.get('id')} نرسیده.\n"
        f"بازه فعلی: {format_range(start, end)}\n\n"
        "فعلاً هیچ خبری نمی‌رود.\n"
        "اگر می‌خوای الان شروع شود، از تنظیمات کانال زمان خاموشی را تغییر بده."
    )


def _resume_text(channel, already=False):
    channel_id = (channel or {}).get("id") or "کانال"

    if already:
        text = f"✅ ربات از قبل در {channel_id} فعال است."
    else:
        text = f"▶️ ارسال شروع شد\n\nاز الان در {channel_id} خبر می‌ذارم."

    if channel and not is_24h(channel) and not is_channel_open(channel):
        text = (
            f"▶️ ارسال {channel_id} روشن شد\n\n"
            + _quiet_block_text(channel)
        )

    return text


def _force_join_text(missing_channel=None):
    """
    متن جوین اجباری.

    اگر کانال خاصی پیدا شده باشد،
    همان کانالی که کاربر هنوز عضو آن نیست نمایش داده می‌شود.
    """

    if isinstance(missing_channel, dict):
        username = str(
            missing_channel.get("username") or ""
        ).strip()

        channel_id = str(
            missing_channel.get("id") or ""
        ).strip()

        if username:
            if not username.startswith("@"):
                username = "@" + username

            channel_name = username

        elif channel_id:
            channel_name = channel_id

        else:
            channel_name = "کانال موردنظر"

        return (
            "🔒 برای استفاده از ربات باید در همه کانال‌های اطلاع‌رسانی عضو باشی.\n\n"
            f"❌ هنوز عضو این کانال نیستی:\n"
            f"📢 {channel_name}\n\n"
            "بعد از عضویت روی «✅ عضو شدم» بزن."
        )

    return (
        "🔒 برای استفاده از ربات باید در همه کانال‌های اطلاع‌رسانی عضو باشی.\n\n"
        "❌ هنوز عضو همه کانال‌ها نیستی.\n\n"
        "بعد از عضویت روی «✅ عضو شدم» بزن."
    )


def home_text(user_id):
    user = get_user(user_id) or {}
    info = subscription_info(user_id)
    channels = user.get("channels") or []
    limit = max_channels_for(user_id) or 1

    if not info["active"]:
        limit = 1
        remain_line = "⏳ مدت باقی‌مانده: ۰ روز"
        sub_line = "📋 اشتراک شما: ندارد"
    else:
        total = info["total"] or info["remaining"]
        remain_line = f"⏳ مدت باقی‌مانده: {info['remaining']}/{total} روز"
        icon = "🎁" if info["type"] == "free" else "⭐"
        sub_line = f"{icon} اشتراک شما: {info['label']}"

    name = user.get("first_name") or "کاربر"

    return (
        f"👋 سلام {name}\n"
        "━━━━━━━━━━━━━━\n"
        f"{sub_line}\n"
        f"{remain_line}\n"
        f"📢 کانال‌های شما: {len(channels)}/{limit}\n"
        "━━━━━━━━━━━━━━\n"
        "از دکمه‌های زیر یکی را انتخاب کن."
    )


def home_components(user_id):
    info = subscription_info(user_id)
    user = get_user(user_id) or {}

    show_free = (
        (not info["active"])
        and (not user.get("free_claimed"))
    )

    keyboard = home_inline_menu(
        show_free=show_free
    )

    if is_admin(user_id):
        keyboard.add(
            InlineKeyboardButton(
                "🛠 پنل مدیریت",
                callback_data="m_admin",
            ),
            row=8,
        )

    return keyboard


async def show_home(target, user_id, reply=False):
    _remember_user(target)

    text = home_text(user_id)
    components = home_components(user_id)

    if reply and callable(getattr(target, "reply", None)):
        await target.reply(
            text,
            components=components,
        )
        return

    await edit_message(
        target,
        text,
        components,
    )


def _start_key(message):
    user_id = (
        message.from_user.id
        if message.from_user
        else 0
    )

    mid = (
        getattr(message, "message_id", None)
        or getattr(message, "id", None)
        or id(message)
    )

    return f"{user_id}:{mid}"


async def handle_start(message: Message):
    if message.from_user is None:
        return

    key = _start_key(message)
    now = time.time()

    last = _START_SEEN.get(key, 0)

    if now - last < 1.2:
        return

    _START_SEEN[key] = now

    if len(_START_SEEN) > 300:
        cutoff = now - 60

        for item in list(_START_SEEN):
            if _START_SEEN[item] < cutoff:
                _START_SEEN.pop(item, None)

    user = message.from_user

    add_user(
        user.id,
        user.first_name,
        user.username,
    )

    # =====================================================
    # Force Join - بررسی کاملاً تازه
    # =====================================================

    if is_force_join_enabled():

        missing_channel = get_user_missing_channel(
            user.id
        )

        if missing_channel is not None:
            await message.reply(
                _force_join_text(
                    missing_channel
                ),
                components=force_join_keyboard(),
            )
            return

    # =====================================================
    # Home
    # =====================================================

    await message.reply(
        home_text(user.id),
        components=home_components(user.id),
    )


async def on_message(message: Message):
    if message.from_user is None:
        return

    text = (message.content or "").strip()

    if text == "/start" or text.startswith("/start "):
        await handle_start(message)
        return


async def on_callback(callback: CallbackQuery):
    data = callback.data or ""
    user_id = callback.from_user.id

    _remember_user(callback)

    user = get_user(user_id) or {}
    channels = user.get("channels") or []

    if data == "m_home":
        clear_state(user_id)

        await show_home(
            callback,
            user_id,
        )
        return

    if data == "m_admin":
        if not is_admin(user_id):
            await edit_message(
                callback,
                "🚫 این بخش فقط برای ادمین است.",
                home_components(user_id),
            )
            return

        from handlers.admin_panel import admin_menu

        await edit_message(
            callback,
            "🛠 پنل مدیریت\n\nیک گزینه را انتخاب کن.",
            admin_menu(),
        )
        return

    if data == "m_settings":
        if not has_subscription(user_id):
            await edit_message(
                callback,
                _need_sub_text(),
                home_components(user_id),
            )
            return

        if not channels:
            await edit_message(
                callback,
                "📢 هنوز کانالی ثبت نشده.\n"
                "اول از «افزودن کانال» کانالت را ثبت کن.",
                home_components(user_id),
            )
            return

        await edit_message(
            callback,
            "⚙️ کدام کانال را می‌خوای تنظیم کنی؟",
            channel_inline_menu(channels),
        )
        return

    if data == "m_add":
        if not has_subscription(user_id):
            await edit_message(
                callback,
                _need_sub_text(),
                home_components(user_id),
            )
            return

        limit = max_channels_for(user_id)

        if len(channels) >= limit:
            await edit_message(
                callback,
                f"🛑 سقف کانال اشتراک شما {limit} تاست.\n"
                "برای سقف بیشتر، اشتراک پولی بخر.",
                home_components(user_id),
            )
            return

        set_state(
            user_id,
            "add_channel",
            {},
        )

        await edit_message(
            callback,
            "➕ آیدی کانال را بفرست.\n\n"
            "مثال: @mychannel\n"
            "ربات باید در کانال ادمین باشد.",
            back_only(),
        )
        return

    if data == "m_pause":
        if not has_subscription(user_id):
            await edit_message(
                callback,
                _need_sub_text(),
                home_components(user_id),
            )
            return

        if not channels:
            await edit_message(
                callback,
                "📢 اول یک کانال ثبت کن.",
                home_components(user_id),
            )
            return

        if len(channels) == 1:
            set_channel_status(
                user_id,
                channels[0]["id"],
                "paused",
            )

            await edit_message(
                callback,
                f"⏸️ ارسال متوقف شد\n\n"
                f"از الان دیگر در {channels[0]['id']} خبری نمی‌ذارم.",
                home_components(user_id),
            )
            return

        await edit_message(
            callback,
            "⏸️ کدام کانال متوقف شود؟",
            channel_pick_menu(
                channels,
                "pause_",
            ),
        )
        return

    if data.startswith("pause_"):
        channel_id = data.replace(
            "pause_",
            "",
            1,
        )

        set_channel_status(
            user_id,
            channel_id,
            "paused",
        )

        await edit_message(
            callback,
            f"⏸️ ارسال متوقف شد\n\n"
            f"دیگر در {channel_id} خبری نمی‌ذارم.",
            home_components(user_id),
        )
        return

    if data == "m_resume":
        if not has_subscription(user_id):
            await edit_message(
                callback,
                _need_sub_text(),
                home_components(user_id),
            )
            return

        if not channels:
            await edit_message(
                callback,
                "📢 اول یک کانال ثبت کن.",
                home_components(user_id),
            )
            return

        if len(channels) == 1:
            channel = channels[0]
            already = (
                channel.get("status")
                == "active"
            )

            if not already:
                set_channel_status(
                    user_id,
                    channel["id"],
                    "active",
                )

            await edit_message(
                callback,
                _resume_text(
                    channel,
                    already=already,
                ),
                home_components(user_id),
            )
            return

        await edit_message(
            callback,
            "▶️ کدام کانال شروع شود؟",
            channel_pick_menu(
                channels,
                "resume_",
            ),
        )
        return

    if data.startswith("resume_"):
        channel_id = data.replace(
            "resume_",
            "",
            1,
        )

        current = _find_channel(
            channels,
            channel_id,
        )

        already = bool(
            current
            and current.get("status") == "active"
        )

        if not already:
            set_channel_status(
                user_id,
                channel_id,
                "active",
            )

        await edit_message(
            callback,
            _resume_text(
                current or {"id": channel_id},
                already=already,
            ),
            home_components(user_id),
        )
        return

    if data == "m_buy":
        await edit_message(
            callback,
            "💳 خرید اشتراک\n\n"
            "تعرفه موردنظرت را انتخاب کن.",
            plans_menu(),
        )
        return

    if data == "m_license":
        set_state(
            user_id,
            "enter_license",
            {},
        )

        await edit_message(
            callback,
            "🔑 ورود کد لایسنس\n\n"
            "کدی که برایت ارسال شده را همین جا بفرست.",
            back_only(),
        )
        return

    if data == "m_free":
        ok, result = claim_free_subscription(
            user_id,
            getattr(
                callback.from_user,
                "first_name",
                None,
            ),
            getattr(
                callback.from_user,
                "username",
                None,
            ),
        )

        if result == "already":
            await edit_message(
                callback,
                "✅ همین حالا اشتراک فعال داری.",
                home_components(user_id),
            )
            return

        if result == "claimed":
            await edit_message(
                callback,
                "🎁 اشتراک رایگان قبلاً گرفته شده.",
                home_components(user_id),
            )
            return

        if not ok:
            await edit_message(
                callback,
                "⚠️ اشتراک ذخیره نشد. دوباره بزن.",
                home_components(user_id),
            )
            return

        await show_home(
            callback,
            user_id,
        )
        return

    if data == "m_support":
        await edit_message(
            callback,
            "📞 پشتیبانی\n\n👤 @pv_ahzar",
            home_components(user_id),
        )
        return
