from bale import CallbackQuery, Message, InlineKeyboardMarkup

from client import bot
from bans import is_banned
from admin_store import is_admin
from ui import edit_message


BAN_TEXT = "حساب شما توسط پشتیبانی بن شد."


async def _safe(handler, argument):
    if handler is None:
        return
    try:
        await handler(argument)
    except Exception as error:
        print("handler error:", error)


@bot.event
async def on_callback(callback: CallbackQuery):
    user = callback.from_user
    if user and is_banned(user.id) and not is_admin(user.id):
        await edit_message(callback, BAN_TEXT, InlineKeyboardMarkup())
        return

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

    for module in (
        admin_complete,
        admin_panel,
        home,
        shop,
        channel_settings,
        footer_text,
        comments,
        stats,
    ):
        await _safe(getattr(module, "on_callback", None), callback)


@bot.event
async def on_message(message: Message):
    if message.from_user is None:
        return
    user_id = message.from_user.id
    if is_banned(user_id) and not is_admin(user_id):
        await message.reply(BAN_TEXT)
        return

    text = (message.content or "").strip()
    if text == "/start" or text.startswith("/start "):
        from handlers.home import handle_start
        await _safe(handle_start, message)
        return

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
    )

    for module in (
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
    ):
        await _safe(getattr(module, "on_message", None), message)
