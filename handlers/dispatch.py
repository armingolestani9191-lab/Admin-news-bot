from bale import CallbackQuery, Message, InlineKeyboardMarkup

from client import bot
from bans import is_banned
from admin_store import is_admin
from ui import edit_message, answer_callback
from states import get_state
from once import once
from users import add_user


BAN_TEXT = "حساب شما توسط پشتیبانی بن شد."

_CB = None
_MSG = None


def _touch_user(user):
    if user is None:
        return
    try:
        add_user(
            user.id,
            getattr(user, "first_name", None),
            getattr(user, "username", None),
        )
    except Exception:
        pass


def _load_cb():
    global _CB
    if _CB is None:
        from handlers import (
            admin_complete,
            admin_panel,
            home,
            shop,
            channel_settings,
            footer_text,
            comments,
            stats,
        )
        _CB = {
            "admin_complete": admin_complete,
            "admin_panel": admin_panel,
            "home": home,
            "shop": shop,
            "channel_settings": channel_settings,
            "footer_text": footer_text,
            "comments": comments,
            "stats": stats,
        }
    return _CB


def _load_msg():
    global _MSG
    if _MSG is None:
        from handlers import (
            admin_complete,
            admin_panel,
            admin_system,
            shop,
            add_channel,
            home,
            footer_text,
            comments,
            navigation,
            channel,
            profile,
            support,
            help,
            channel_settings,
        )
        _MSG = {
            "admin_complete": admin_complete,
            "admin_panel": admin_panel,
            "admin_system": admin_system,
            "shop": shop,
            "add_channel": add_channel,
            "home": home,
            "footer_text": footer_text,
            "comments": comments,
            "navigation": navigation,
            "channel": channel,
            "profile": profile,
            "support": support,
            "help": help,
            "channel_settings": channel_settings,
        }
    return _MSG


async def _safe(handler, argument):
    if handler is None:
        return
    try:
        await handler(argument)
    except Exception as error:
        print("handler error:", error)


def _callback_modules(data):
    mods = _load_cb()
    data = data or ""

    if data in ("ignore", "ad_ignore"):
        names = ()

    elif data == "check_force_join":
        names = ("admin_panel",)

    elif data.startswith("ad_") or data.startswith("channel_stats_"):
        names = ("admin_complete", "admin_panel")

    elif data == "m_comment" or data.startswith("cmt"):
        names = ("comments",)

    elif data == "m_stats" or data.startswith("stats_"):
        names = ("stats",)

    elif (
        data.startswith("plan_")
        or data.startswith("pay_")
        or data.startswith("adm_")
    ):
        names = ("shop",)

    elif data in ("csave", "cat_save") or data.startswith((
        "csel_",
        "cat_",
        "time_",
        "stime_",
        "img_",
        "emoji_",
        "delete_",
        "yesdel_",
        "nodel_",
        "quiet_",
        "q24_",
        "qpre_",
        "qcus_",
    )):
        names = ("channel_settings",)

    elif (
        data.startswith("channel_")
        and not data.startswith("channel_stats_")
    ):
        names = ("channel_settings",)

    elif data.startswith("link_") or data.startswith("footer_"):
        names = ("footer_text",)

    elif (
        data.startswith("m_")
        or data.startswith("pause_")
        or data.startswith("resume_")
    ):
        names = ("home",)

    else:
        names = (
            "home",
            "channel_settings",
            "admin_panel",
        )

    return [
        mods[name]
        for name in names
        if name in mods
    ]


def _message_modules(user_id, text):
    mods = _load_msg()
    name = (get_state(user_id) or {}).get("state")

    if name in (
        "admin_card",
        "admin_user_find",
        "admin_user_msg",
    ):
        keys = ("admin_complete",)

    elif name in (
        "admin_bc",
        "admin_join_add",
        "admin_join_del",
        "admin_add",
        "admin_del",
    ):
        keys = ("admin_panel",)

    elif name in (
        "enter_license",
        "choose_pay",
        "card_info",
        "gift_code",
        "wait_receipt",
        "admin_msg",
    ):
        keys = ("shop",)

    elif name == "add_channel":
        keys = ("add_channel", "navigation")

    elif name in (
        "footer_text",
        "footer_confirm",
        "footer_manage",
    ):
        keys = ("footer_text", "navigation")

    elif name in (
        "comment_text",
        "comment_edit",
    ):
        keys = ("comments", "navigation")

    elif name in (
        "category_select",
        "quiet_custom",
    ):
        keys = ("channel_settings", "navigation")

    elif text in (
        "🏠 منوی اصلی",
        "🔙 بازگشت",
    ):
        keys = ("navigation",)

    elif text == "📢 کانال‌های من":
        keys = ("channel",)

    elif text == "👤 پروفایل":
        keys = ("profile",)

    elif text == "📞 پشتیبانی":
        keys = ("support",)

    elif text == "📖 راهنما":
        keys = ("help",)

    elif text in (
        "📊 آمار کاربران",
        "📢 آمار کانال‌ها",
        "📰 آمار اخبار",
        "👤 مدیریت کاربران",
        "📺 مدیریت کانال‌ها",
        "👮 ادمین‌ها",
        "📨 ارسال همگانی",
        "⚙️ تنظیمات ربات",
        "🔒 جوین اجباری",
        "🛠 پنل مدیریت",
    ):
        keys = (
            "admin_system",
            "admin_panel",
            "admin_complete",
        )

    elif text == "/بکاپ":
        keys = ("admin_system",)

    else:
        keys = ("navigation",)

    return [
        mods[key]
        for key in keys
        if key in mods
    ]


@bot.event
async def on_callback(callback: CallbackQuery):
    if not once(callback, "dispatch_cb"):
        return

    answer_callback(callback)

    user = callback.from_user

    if user and is_banned(user.id) and not is_admin(user.id):
        await edit_message(
            callback,
            BAN_TEXT,
            InlineKeyboardMarkup(),
        )
        return

    modules = _callback_modules(
        callback.data or ""
    )

    if not modules:
        return

    for module in modules:
        await _safe(
            getattr(module, "on_callback", None),
            callback,
        )


@bot.event
async def on_message(message: Message):
    if not once(message, "dispatch_msg"):
        return

    if message.from_user is None:
        return

    _touch_user(message.from_user)

    user_id = message.from_user.id

    if is_banned(user_id) and not is_admin(user_id):
        await message.reply(BAN_TEXT)
        return

    text = (message.content or "").strip()

    if text == "/start" or text.startswith("/start "):
        from handlers.home import handle_start

        await _safe(
            handle_start,
            message,
        )
        return

    for module in _message_modules(
        user_id,
        text,
    ):
        await _safe(
            getattr(module, "on_message", None),
            message,
    )
