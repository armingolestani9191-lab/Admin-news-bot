from bale import CallbackQuery, Message

from ui import edit_message
from keyboards import (
    footer_preview_menu,
    footer_manage_menu,
    footer_delete_menu,
    channel_settings_menu,
)
from states import set_state, get_state, clear_state
from users import update_footer_text, get_user


def _settings_components(user_id, channel_id):
    send_image = True
    show_emoji = True
    user = get_user(user_id) or {}
    for channel in user.get("channels") or []:
        if str(channel.get("id") or "") == str(channel_id):
            send_image = channel.get("send_image", True)
            show_emoji = channel.get("show_emoji", True)
            break
    return channel_settings_menu(channel_id, send_image, show_emoji)


async def _show_settings(target, user_id, channel_id, prefix=""):
    text = f"{prefix}⚙️ تنظیمات کانال\n\n📢 {channel_id}"
    await edit_message(target, text, _settings_components(user_id, channel_id))


async def on_callback(callback: CallbackQuery):
    data = callback.data or ""
    user_id = callback.from_user.id

    if data.startswith("link_"):
        channel_id = data.replace("link_", "", 1)
        user = get_user(user_id) or {}
        footer = ""
        for channel in user.get("channels") or []:
            if str(channel.get("id") or "") == str(channel_id):
                footer = channel.get("footer_text", "") or ""
                break
        if footer:
            set_state(user_id, "footer_manage", {"channel_id": channel_id})
            await edit_message(
                callback,
                "✏️ متن فعلی پایین خبر\n\n"
                "━━━━━━━━━━━━━━\n\n"
                f"{footer}\n\n"
                "━━━━━━━━━━━━━━\n\n"
                "یکی از گزینه‌ها را انتخاب کن.",
                footer_manage_menu(),
            )
            return
        set_state(user_id, "footer_text", {"channel_id": channel_id})
        await edit_message(
            callback,
            "✏️ تنظیم متن پایین خبر\n\n"
            f"📢 کانال:\n{channel_id}\n\n"
            "متن دلخواه را بفرست.\n"
            "این متن زیر تمام خبرهای این کانال نمایش داده می‌شود.",
        )
        return

    if data == "footer_save":
        state = get_state(user_id)
        if state.get("state") != "footer_confirm":
            return
        payload = state.get("data") or {}
        channel_id = payload.get("channel_id")
        text = payload.get("text")
        result = update_footer_text(user_id, channel_id, text)
        clear_state(user_id)
        if result:
            await _show_settings(callback, user_id, channel_id, "✅ متن پایین خبر ذخیره شد.\n\n")
        else:
            await edit_message(callback, "❌ خطا در ذخیره متن.")
        return

    if data == "footer_edit":
        state = get_state(user_id)
        set_state(user_id, "footer_text", {"channel_id": (state.get("data") or {}).get("channel_id")})
        await edit_message(
            callback,
            "✏️ ویرایش متن پایین خبر\n\n"
            "متن جدید را بفرست.\n"
            "این متن جایگزین متن قبلی می‌شود.",
        )
        return

    if data == "footer_delete":
        state = get_state(user_id)
        if state.get("state") != "footer_manage":
            return
        await edit_message(
            callback,
            "⚠️ آیا از حذف متن پایین خبر مطمئن هستید؟",
            footer_delete_menu(),
        )
        return

    if data == "footer_delete_yes":
        state = get_state(user_id)
        if state.get("state") != "footer_manage":
            return
        channel_id = (state.get("data") or {}).get("channel_id")
        result = update_footer_text(user_id, channel_id, "")
        clear_state(user_id)
        if result:
            await _show_settings(callback, user_id, channel_id, "✅ متن پایین خبر حذف شد.\n\n")
        else:
            await edit_message(callback, "❌ خطا در حذف متن.")
        return

    if data == "footer_delete_no":
        state = get_state(user_id)
        if state.get("state") != "footer_manage":
            return
        await edit_message(callback, "❌ حذف متن لغو شد.")
        return

    if data == "footer_cancel":
        clear_state(user_id)
        await edit_message(callback, "❌ عملیات لغو شد.")
        return


async def on_message(message: Message):
    if message.from_user is None:
        return
    user_id = message.from_user.id
    state = get_state(user_id)
    if state.get("state") != "footer_text":
        return
    text = (message.content or "").strip()
    if text in ("🔙 بازگشت", "🏠 منوی اصلی", "❌ انصراف"):
        clear_state(user_id)
        return
    payload = dict(state.get("data") or {})
    payload["text"] = text
    set_state(user_id, "footer_confirm", payload)
    await message.reply(
        "👀 پیش‌نمایش متن پایین خبر\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "آیا از ذخیره این متن مطمئن هستی؟",
        components=footer_preview_menu(),
    )
