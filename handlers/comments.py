from bale import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from client import bot
from ui import edit_message
from users import get_user, load_users, _patch_channel
from keyboards import channel_pick_menu
from states import set_state, get_state, clear_state
from subscription import has_subscription
from handlers.home import home_components, back_only
from commenter import post_comment


PRESETS = [
    "به کامنت‌های یکدیگر احترام بگذارید",
    "ری‌اکشن یادت نره",
    "کامنت یادت نره",
]


def _need_sub():
    return "🔒 اول اشتراک را فعال کن."


def find_channel(user, channel_id):
    for item in user.get("channels") or []:
        if item.get("id") == channel_id:
            return item
    return None


def _keys_of_chat(obj):
    keys = set()

    if not obj:
        return keys

    username = getattr(obj, "username", None)

    chat_id = str(
        getattr(obj, "id", "")
        or getattr(obj, "chat_id", "")
        or ""
    )

    if username:
        username = str(username).lstrip("@")

        keys.add("@" + username)
        keys.add(username.lower())

    if chat_id:
        keys.add(chat_id)

    return keys


def find_live_channel_by_keys(keys):
    for user_id, user in load_users().items():

        if not isinstance(user, dict):
            continue

        for channel in user.get("channels") or []:

            cid = str(
                channel.get("id") or ""
            )

            normalized = cid.lstrip("@").lower()

            if (
                cid in keys
                or normalized in keys
                or ("@" + normalized) in keys
            ):
                return str(user_id), channel

    return None, None


def comment_text_view(channel):
    on = bool(
        channel.get("comment_on")
    )

    text = (
        channel.get("comment_text") or ""
    ).strip() or "ندارد"

    status = (
        "🟢 روشن"
        if on
        else "🔴 خاموش"
    )

    return (
        f"💬 کامنت {channel.get('id')}\n"
        "━━━━━━━━━━━━━━\n"
        f"وضعیت: {status}\n"
        f"متن: {text}\n\n"
        "متن فقط داخل دیدگاه نوشته می‌شود.\n"
        "ربات باید ادمین گروه دیدگاه هم باشد."
    )


def comment_menu(channel):
    on = bool(
        channel.get("comment_on")
    )

    cid = channel["id"]

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🔴 خاموش کردن"
            if on
            else "🟢 روشن کردن",
            callback_data=f"cmt_toggle_{cid}",
        ),
        row=1,
    )

    keyboard.add(
        InlineKeyboardButton(
            "✏️ متن دلخواه",
            callback_data=f"cmt_custom_{cid}",
        ),
        row=2,
    )

    keyboard.add(
        InlineKeyboardButton(
            "💬 احترام بگذارید",
            callback_data=f"cmt_pre_0_{cid}",
        ),
        row=3,
    )

    keyboard.add(
        InlineKeyboardButton(
            "👍 ری‌اکشن یادت نره",
            callback_data=f"cmt_pre_1_{cid}",
        ),
        row=4,
    )

    keyboard.add(
        InlineKeyboardButton(
            "📝 کامنت یادت نره",
            callback_data=f"cmt_pre_2_{cid}",
        ),
        row=5,
    )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="m_home",
        ),
        row=6,
    )

    return keyboard


async def show_comment_panel(
    callback,
    user_id,
    channel_id,
):
    user = get_user(user_id) or {}

    channel = find_channel(
        user,
        channel_id,
    )

    if not channel:
        await edit_message(
            callback,
            "کانال پیدا نشد.",
            home_components(user_id),
        )
        return

    set_state(
        user_id,
        "comment_edit",
        {
            "channel_id": channel_id,
        },
    )

    await edit_message(
        callback,
        comment_text_view(channel),
        comment_menu(channel),
    )


def save_comment(
    user_id,
    channel_id,
    text=None,
    enabled=None,
):
    payload = {}

    if text is not None:
        payload["comment_text"] = text[:400]

    if enabled is not None:
        payload["comment_on"] = bool(enabled)

    if payload:
        _patch_channel(
            user_id,
            channel_id,
            payload,
        )

    return find_channel(
        get_user(user_id) or {},
        channel_id,
    )


@bot.event
async def on_callback(callback: CallbackQuery):
    data = callback.data or ""

    user_id = callback.from_user.id

    user = get_user(user_id) or {}

    channels = user.get("channels") or []

    if data == "m_comment":

        if not has_subscription(user_id):
            await edit_message(
                callback,
                _need_sub(),
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
            await show_comment_panel(
                callback,
                user_id,
                channels[0]["id"],
            )
            return

        await edit_message(
            callback,
            "💬 کامنت کدام کانال را می‌خوای؟",
            channel_pick_menu(
                channels,
                "cmtch_",
            ),
        )
        return

    if data.startswith("cmtch_"):

        await show_comment_panel(
            callback,
            user_id,
            data.replace(
                "cmtch_",
                "",
                1,
            ),
        )
        return

    if data.startswith("cmt_toggle_"):

        channel_id = data.replace(
            "cmt_toggle_",
            "",
            1,
        )

        channel = find_channel(
            user,
            channel_id,
        )

        if not channel:
            return

        new_value = not bool(
            channel.get("comment_on")
        )

        if new_value and not (
            channel.get("comment_text") or ""
        ).strip():

            await edit_message(
                callback,
                "⚠️ اول یک متن برای کامنت انتخاب کن.",
                comment_menu(channel),
            )
            return

        channel = save_comment(
            user_id,
            channel_id,
            enabled=new_value,
        )

        await edit_message(
            callback,
            comment_text_view(channel),
            comment_menu(channel),
        )

        return

    if data.startswith("cmt_custom_"):

        channel_id = data.replace(
            "cmt_custom_",
            "",
            1,
        )

        set_state(
            user_id,
            "comment_text",
            {
                "channel_id": channel_id,
            },
        )

        await edit_message(
            callback,
            "✏️ متن کامنت را بفرست.\n"
            "مثال: ری‌اکشن یادت نره",
            back_only(),
        )

        return

    if data.startswith("cmt_pre_"):

        rest = data.replace(
            "cmt_pre_",
            "",
            1,
        )

        index_s, sep, channel_id = rest.partition("_")

        if not sep:
            channel_id = (
                (get_state(user_id).get("data") or {})
                .get("channel_id")
            )

        try:
            index = int(index_s)
        except Exception:
            return

        if (
            index < 0
            or index >= len(PRESETS)
            or not channel_id
        ):
            return

        channel = save_comment(
            user_id,
            channel_id,
            text=PRESETS[index],
            enabled=True,
        )

        view = channel or {
            "id": channel_id,
            "comment_on": True,
            "comment_text": PRESETS[index],
        }

        await edit_message(
            callback,
            "✅ متن ذخیره شد و کامنت روشن شد.\n\n"
            + comment_text_view(view),
            comment_menu(view),
        )

        return


# ---------------------------------------------------------
# منطق اصلی کامنت پست کانال
# ---------------------------------------------------------

def handle_channel_post(message):
    """
    فقط پست واقعی کانال را پردازش می‌کند.

    گروه و سوپرگروه اینجا اصلاً وارد نمی‌شوند.
    """

    chat = getattr(
        message,
        "chat",
        None,
    )

    if not chat:
        return False

    chat_type = str(
        getattr(chat, "type", "") or ""
    )

    # فقط CHANNEL
    if chat_type != "channel":
        return False

    owner_id, channel = find_live_channel_by_keys(
        _keys_of_chat(chat)
    )

    # کانال ثبت نشده برای این ربات
    if not channel:
        return True

    # -------------------------------------------------
    # کامنت خاموش = هیچ کاری
    # -------------------------------------------------
    if not channel.get("comment_on"):
        return True

    # -------------------------------------------------
    # متن کامنت وجود ندارد = هیچ کاری
    # -------------------------------------------------
    text = (
        channel.get("comment_text") or ""
    ).strip()

    if not text:
        return True

    # -------------------------------------------------
    # شناسه پست کانال
    # -------------------------------------------------
    message_id = (
        getattr(message, "message_id", None)
        or getattr(message, "id", None)
    )

    if not message_id:
        print(
            f"⚠️ شناسه پست کانال {channel.get('id')} پیدا نشد."
        )
        return True

    try:
        message_id = int(message_id)
    except Exception:
        return True

    # -------------------------------------------------
    # جلوگیری از کامنت تکراری برای همان پست
    # -------------------------------------------------
    previous_id = channel.get(
        "last_commented_post_id"
    )

    try:
        if previous_id is not None:
            if int(previous_id) == message_id:
                return True
    except Exception:
        pass

    print(
        f"💬 پست جدید کانال {channel.get('id')} "
        f"| post_id={message_id}"
    )

    # -------------------------------------------------
    # فقط یک بار تلاش برای کامنت زیر همان پست
    # -------------------------------------------------
    result = post_comment(
        channel.get("id"),
        text,
        reply_to=message_id,
    )

    if result.get("ok"):
        _patch_channel(
            owner_id,
            channel.get("id"),
            {
                "last_commented_post_id": message_id,
            },
        )

        print(
            f"✅ کامنت کانال {channel.get('id')} "
            f"برای پست {message_id} ارسال شد."
        )

    else:
        print(
            f"⚠️ کامنت کانال {channel.get('id')} "
            f"برای پست {message_id} ارسال نشد: "
            f"{result.get('description', '')[:160]}"
        )

    return True


@bot.event
async def on_message(message: Message):

    # -------------------------------------------------
    # این handler فقط برای سازگاری قبلی نگه داشته شده.
    # Router مرکزی dispatch پست‌های کانال را مستقیماً
    # به handle_channel_post می‌دهد.
    # -------------------------------------------------

    chat = getattr(
        message,
        "chat",
        None,
    )

    chat_type = str(
        getattr(chat, "type", "") or ""
    )

    # پیام‌های گروه دیدگاه:
    # هیچ پاسخ خودکاری ندارند.
    if chat_type in (
        "group",
        "supergroup",
    ):
        return

    if chat_type == "channel":
        handle_channel_post(message)
        return

    if message.from_user is None:
        return

    user_id = message.from_user.id

    state = get_state(user_id)

    if state.get("state") != "comment_text":
        return

    channel_id = (
        state.get("data") or {}
    ).get("channel_id")

    text = (
        message.content or ""
    ).strip()

    if not channel_id or not text:
        return

    channel = save_comment(
        user_id,
        channel_id,
        text=text,
        enabled=True,
    )

    clear_state(user_id)

    view = channel or {
        "id": channel_id,
        "comment_on": True,
        "comment_text": text,
    }

    await message.reply(
        "✅ متن کامنت ذخیره شد و فعال شد.\n\n"
        + comment_text_view(view),
        components=comment_menu(view),
            )
