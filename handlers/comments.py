from bale import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from client import bot
from ui import edit_message
from users import (
    get_user,
    load_users,
    _patch_channel,
)
from keyboards import channel_pick_menu
from states import (
    set_state,
    get_state,
    clear_state,
)
from subscription import has_subscription
from handlers.home import (
    home_components,
    back_only,
)
from commenter import (
    post_comment,
    get_linked_chat,
)


# =========================================================
# PRESETS
# =========================================================

PRESETS = [
    "به کامنت‌های یکدیگر احترام بگذارید",
    "ری‌اکشن یادت نره",
    "کامنت یادت نره",
]


# =========================================================
# BASIC HELPERS
# =========================================================

def _need_sub():
    return "🔒 اول اشتراک را فعال کن."


def _is_comment_enabled(channel):
    """
    کامنت روشن/خاموش را به شکل امن بررسی می‌کند.

    هم bool واقعی را پشتیبانی می‌کند،
    هم مقادیر قدیمی مثل "true" / "false".
    """

    if not isinstance(channel, dict):
        return False

    value = channel.get("comment_on")

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return bool(value)

    value = str(value).strip().lower()

    return value in (
        "1",
        "true",
        "yes",
        "on",
        "روشن",
        "فعال",
    )


def find_channel(user, channel_id):
    """
    پیدا کردن کانال کاربر.
    """

    if not isinstance(user, dict):
        return None

    target = str(
        channel_id or ""
    ).strip().lower()

    if not target:
        return None

    for item in user.get("channels") or []:

        if not isinstance(item, dict):
            continue

        current = str(
            item.get("id") or ""
        ).strip().lower()

        if current == target:
            return item

    return None


def _normalize_channel_key(value):
    """
    نرمال‌سازی شناسه کانال برای مقایسه.
    """

    value = str(
        value or ""
    ).strip()

    if not value:
        return ""

    return value.lower()


def _keys_of_chat(obj):
    """
    کلیدهای قابل استفاده از Chat بله.
    """

    keys = set()

    if not obj:
        return keys

    username = getattr(
        obj,
        "username",
        None,
    )

    chat_id = (
        getattr(obj, "id", None)
        or getattr(obj, "chat_id", None)
    )

    if username:
        username = str(
            username
        ).strip().lstrip("@")

        if username:
            keys.add(
                "@" + username.lower()
            )

            keys.add(
                username.lower()
            )

    if chat_id is not None:
        chat_id = str(
            chat_id
        ).strip()

        if chat_id:
            keys.add(chat_id)
            keys.add(chat_id.lower())

    return keys


def find_live_channel_by_keys(keys):
    """
    پیدا کردن کانال ثبت‌شده در دیتابیس
    بر اساس ID یا username.
    """

    if not keys:
        return None, None

    normalized_keys = set()

    for key in keys:
        key = str(
            key or ""
        ).strip().lower()

        if not key:
            continue

        normalized_keys.add(key)

        if key.startswith("@"):
            normalized_keys.add(
                key[1:]
            )
        else:
            normalized_keys.add(
                "@" + key
            )

    users = load_users()

    for user_id, user in users.items():

        if not isinstance(user, dict):
            continue

        for channel in user.get("channels") or []:

            if not isinstance(channel, dict):
                continue

            channel_id = str(
                channel.get("id") or ""
            ).strip()

            if not channel_id:
                continue

            normalized_channel = (
                channel_id.lower()
            )

            channel_without_at = (
                normalized_channel.lstrip("@")
            )

            possible = {
                normalized_channel,
                channel_without_at,
                "@" + channel_without_at,
            }

            if possible.intersection(
                normalized_keys
            ):
                return (
                    str(user_id),
                    channel,
                )

    return None, None


# =========================================================
# UI
# =========================================================

def comment_text_view(channel):
    enabled = _is_comment_enabled(
        channel
    )

    text = (
        channel.get("comment_text") or ""
    ).strip()

    if not text:
        text = "ندارد"

    status = (
        "🟢 روشن"
        if enabled
        else "🔴 خاموش"
    )

    return (
        f"💬 کامنت {channel.get('id')}\n"
        "━━━━━━━━━━━━━━\n"
        f"وضعیت: {status}\n"
        f"متن: {text}\n\n"
        "متن دقیقاً به‌صورت یک پیام عادی "
        "داخل گروه دیدگاه ارسال می‌شود.\n"
        "ربات باید امکان ارسال پیام در گروه دیدگاه را داشته باشد."
    )


def comment_menu(channel):
    enabled = _is_comment_enabled(
        channel
    )

    cid = channel["id"]

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🔴 خاموش کردن"
            if enabled
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
        payload["comment_text"] = str(
            text
        ).strip()[:400]

    if enabled is not None:
        payload["comment_on"] = bool(
            enabled
        )

    if payload:
        success = _patch_channel(
            user_id,
            channel_id,
            payload,
        )

        print(
            f"💾 ذخیره تنظیمات کامنت | "
            f"user={user_id} | "
            f"channel={channel_id} | "
            f"payload={payload} | "
            f"success={success}"
        )

    # دوباره از DB می‌خوانیم تا مطمئن شویم
    # وضعیت تازه نمایش داده می‌شود.
    fresh_user = get_user(
        user_id
    ) or {}

    return find_channel(
        fresh_user,
        channel_id,
    )


# =========================================================
# CALLBACKS
# =========================================================

async def on_callback(callback: CallbackQuery):

    data = callback.data or ""

    user = (
        get_user(
            callback.from_user.id
        )
        or {}
    )

    user_id = callback.from_user.id

    channels = user.get(
        "channels"
    ) or []

    # -----------------------------------------------------
    # MAIN COMMENT MENU
    # -----------------------------------------------------

    if data == "m_comment":

        if not has_subscription(
            user_id
        ):
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

    # -----------------------------------------------------
    # CHANNEL SELECT
    # -----------------------------------------------------

    if data.startswith("cmtch_"):

        channel_id = data.replace(
            "cmtch_",
            "",
            1,
        )

        await show_comment_panel(
            callback,
            user_id,
            channel_id,
        )

        return

    # -----------------------------------------------------
    # TOGGLE
    # -----------------------------------------------------

    if data.startswith(
        "cmt_toggle_"
    ):

        channel_id = data.replace(
            "cmt_toggle_",
            "",
            1,
        )

        # همیشه کاربر را دوباره از DB می‌خوانیم
        # تا مقدار قدیمی استفاده نشود.
        fresh_user = (
            get_user(user_id)
            or {}
        )

        channel = find_channel(
            fresh_user,
            channel_id,
        )

        if not channel:
            print(
                f"⚠️ toggle: channel not found | "
                f"user={user_id} | "
                f"channel={channel_id}"
            )
            return

        current_value = (
            _is_comment_enabled(
                channel
            )
        )

        new_value = not current_value

        # روشن کردن بدون متن مجاز نیست.
        if new_value:

            text = (
                channel.get(
                    "comment_text"
                )
                or ""
            ).strip()

            if not text:

                await edit_message(
                    callback,
                    "⚠️ اول یک متن برای کامنت انتخاب کن.",
                    comment_menu(channel),
                )

                return

        updated = save_comment(
            user_id,
            channel_id,
            enabled=new_value,
        )

        if not updated:

            print(
                f"❌ toggle save failed | "
                f"user={user_id} | "
                f"channel={channel_id}"
            )

            await edit_message(
                callback,
                "❌ ذخیره وضعیت کامنت انجام نشد.",
                comment_menu(channel),
            )

            return

        print(
            f"🔄 وضعیت کامنت تغییر کرد | "
            f"user={user_id} | "
            f"channel={channel_id} | "
            f"{current_value} -> {new_value}"
        )

        await edit_message(
            callback,
            comment_text_view(updated),
            comment_menu(updated),
        )

        return

    # -----------------------------------------------------
    # CUSTOM TEXT
    # -----------------------------------------------------

    if data.startswith(
        "cmt_custom_"
    ):

        channel_id = data.replace(
            "cmt_custom_",
            "",
            1,
        )

        if not find_channel(
            user,
            channel_id,
        ):
            return

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

    # -----------------------------------------------------
    # PRESETS
    # -----------------------------------------------------

    if data.startswith(
        "cmt_pre_"
    ):

        rest = data.replace(
            "cmt_pre_",
            "",
            1,
        )

        index_s, sep, channel_id = (
            rest.partition("_")
        )

        if not sep:

            state = (
                get_state(user_id)
                or {}
            )

            channel_id = (
                state.get("data") or {}
            ).get(
                "channel_id"
            )

        try:
            index = int(
                index_s
            )
        except Exception:
            return

        if (
            index < 0
            or index >= len(PRESETS)
            or not channel_id
        ):
            return

        if not find_channel(
            user,
            channel_id,
        ):
            return

        selected_text = PRESETS[
            index
        ]

        channel = save_comment(
            user_id,
            channel_id,
            text=selected_text,
            enabled=True,
        )

        if not channel:
            return

        print(
            f"📝 preset comment saved | "
            f"user={user_id} | "
            f"channel={channel_id} | "
            f"text={selected_text!r}"
        )

        await edit_message(
            callback,
            "✅ متن ذخیره شد و کامنت روشن شد.\n\n"
            + comment_text_view(
                channel
            ),
            comment_menu(channel),
        )

        return


# =========================================================
# DIRECT CHANNEL POST COMMENT
# =========================================================

def handle_channel_post(message):
    """
    وقتی ربات یک پست کانال را دریافت می‌کند،
    مستقیماً گروه دیدگاه متصل را پیدا می‌کند
    و کامنت را ارسال می‌کند.

    دیگر به forward شدن پست داخل گروه
    وابسته نیستیم.
    """

    chat = getattr(
        message,
        "chat",
        None,
    )

    if not chat:
        print(
            "⚠️ channel post بدون chat دریافت شد."
        )
        return False

    chat_type = str(
        getattr(
            chat,
            "type",
            "",
        )
        or ""
    ).lower()

    if chat_type != "channel":
        return False

    # -----------------------------------------------------
    # FIND CHANNEL
    # -----------------------------------------------------

    keys = _keys_of_chat(
        chat
    )

    print(
        f"📢 Channel post received | "
        f"keys={sorted(keys)}"
    )

    owner_id, channel = (
        find_live_channel_by_keys(
            keys
        )
    )

    if not channel:

        print(
            f"⚠️ کانال در دیتابیس پیدا نشد | "
            f"keys={sorted(keys)}"
        )

        return True

    channel_id = channel.get(
        "id"
    )

    print(
        f"📌 کانال شناسایی شد | "
        f"channel={channel_id} | "
        f"owner={owner_id}"
    )

    # -----------------------------------------------------
    # CHECK ON/OFF
    # -----------------------------------------------------

    if not _is_comment_enabled(
        channel
    ):

        print(
            f"🔴 کامنت خاموش است | "
            f"channel={channel_id}"
        )

        return True

    # -----------------------------------------------------
    # CHECK TEXT
    # -----------------------------------------------------

    text = (
        channel.get(
            "comment_text"
        )
        or ""
    ).strip()

    if not text:

        print(
            f"⚠️ کامنت روشن است ولی متن ندارد | "
            f"channel={channel_id}"
        )

        return True

    # -----------------------------------------------------
    # POST ID
    # -----------------------------------------------------

    message_id = (
        getattr(
            message,
            "message_id",
            None,
        )
        or getattr(
            message,
            "id",
            None,
        )
    )

    try:
        message_id = int(
            message_id
        )
    except Exception:

        print(
            f"⚠️ شناسه پست کانال قابل تشخیص نیست | "
            f"channel={channel_id}"
        )

        return True

    print(
        f"📰 پست کانال | "
        f"channel={channel_id} | "
        f"post_id={message_id}"
    )

    # -----------------------------------------------------
    # DUPLICATE PROTECTION
    # -----------------------------------------------------

    previous_id = channel.get(
        "last_commented_post_id"
    )

    try:

        if (
            previous_id is not None
            and int(previous_id)
            == message_id
        ):

            print(
                f"ℹ️ کامنت این پست قبلاً ارسال شده | "
                f"channel={channel_id} | "
                f"post_id={message_id}"
            )

            return True

    except Exception:
        pass

    # -----------------------------------------------------
    # FIND LINKED DISCUSSION GROUP
    # -----------------------------------------------------

    print(
        f"🔎 در حال پیدا کردن گروه دیدگاه | "
        f"channel={channel_id}"
    )

    group_id = get_linked_chat(
        channel_id
    )

    if not group_id:

        print(
            f"❌ گروه دیدگاه پیدا نشد | "
            f"channel={channel_id}"
        )

        return True

    print(
        f"🔗 گروه دیدگاه پیدا شد | "
        f"channel={channel_id} | "
        f"group={group_id}"
    )

    # -----------------------------------------------------
    # SEND NORMAL MESSAGE
    # -----------------------------------------------------

    print(
        f"📤 ارسال کامنت | "
        f"channel={channel_id} | "
        f"group={group_id} | "
        f"text={text!r}"
    )

    result = post_comment(
        channel_id,
        text,
        group_id=group_id,
    )

    if not isinstance(
        result,
        dict,
    ):
        print(
            f"❌ پاسخ نامعتبر از post_comment | "
            f"channel={channel_id}"
        )
        return True

    if result.get("ok"):

        saved = _patch_channel(
            owner_id,
            channel_id,
            {
                "last_commented_post_id": message_id,
            },
        )

        print(
            f"✅ کامنت ارسال شد | "
            f"channel={channel_id} | "
            f"post_id={message_id} | "
            f"group={group_id} | "
            f"db_saved={saved}"
        )

    else:

        print(
            f"❌ کامنت ارسال نشد | "
            f"channel={channel_id} | "
            f"group={group_id} | "
            f"code={result.get('code')} | "
            f"description={result.get('description', '')}"
        )

    return True


# =========================================================
# DISCUSSION MESSAGE
# =========================================================

def handle_discussion_message(message):
    """
    عمداً هیچ کامنتی از پیام‌های گروه ایجاد نمی‌کنیم.

    این تابع فقط برای سازگاری با کدهای قبلی
    نگه داشته شده است.

    بنابراین اگر کاربر داخل گروه چیزی بنویسد،
    ربات به آن پاسخ کامنت نمی‌دهد.
    """

    chat = getattr(
        message,
        "chat",
        None,
    )

    if not chat:
        return False

    chat_type = str(
        getattr(
            chat,
            "type",
            "",
        )
        or ""
    ).lower()

    if chat_type not in (
        "group",
        "supergroup",
    ):
        return False

    # مهم:
    # هیچ ارسال کامنتی از پیام گروه انجام نمی‌شود.
    return False


# =========================================================
# PRIVATE CUSTOM TEXT
# =========================================================

async def handle_private_comment_text(
    message
):
    """
    ذخیره متن دلخواه کامنت.
    """

    if message.from_user is None:
        return False

    user_id = (
        message.from_user.id
    )

    state = (
        get_state(user_id)
        or {}
    )

    if state.get(
        "state"
    ) != "comment_text":
        return False

    channel_id = (
        state.get("data") or {}
    ).get(
        "channel_id"
    )

    text = (
        message.content or ""
    ).strip()

    if not channel_id:
        return False

    if not text:
        return False

    channel = save_comment(
        user_id,
        channel_id,
        text=text,
        enabled=True,
    )

    clear_state(
        user_id
    )

    view = channel or {
        "id": channel_id,
        "comment_on": True,
        "comment_text": text,
    }

    print(
        f"📝 custom comment saved | "
        f"user={user_id} | "
        f"channel={channel_id} | "
        f"text={text!r}"
    )

    await message.reply(
        "✅ متن کامنت ذخیره شد و فعال شد.\n\n"
        + comment_text_view(
            view
        ),
        components=comment_menu(
            view
        ),
    )

    return True


# =========================================================
# MESSAGE EVENT
# =========================================================

async def on_message(message: Message):

    chat = getattr(
        message,
        "chat",
        None,
    )

    chat_type = str(
        getattr(
            chat,
            "type",
            "",
        )
        or ""
    ).lower()

    # -----------------------------------------------------
    # CHANNEL
    # -----------------------------------------------------

    if chat_type == "channel":

        handle_channel_post(
            message
        )

        return

    # -----------------------------------------------------
    # GROUP
    # -----------------------------------------------------

    if chat_type in (
        "group",
        "supergroup",
    ):

        # هیچ پیام کاربر در گروه
        # نباید کامنت تولید کند.
        return

    # -----------------------------------------------------
    # PRIVATE
    # -----------------------------------------------------

    if message.from_user is None:
        return

    await handle_private_comment_text(
        message
    )
