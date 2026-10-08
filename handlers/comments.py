from bale import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from users import (
    get_user,
    load_users,
    _patch_channel,
)

from ui import edit_message

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
    get_linked_chat,
    send_discussion_reply,
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
# RUNTIME CACHE
# =========================================================

# channel_id -> {
#     post_id: {
#         "owner_id": ...,
#         "text": ...,
#         "group_id": ...,
#         "created_at": ...
#     }
# }

_PENDING_POSTS = {}


# برای جلوگیری از ارسال همزمان دوباره
_IN_FLIGHT = set()


# =========================================================
# BASIC HELPERS
# =========================================================

def _need_sub():
    return "🔒 اول اشتراک را فعال کن."


def _is_comment_enabled(channel):
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


# =========================================================
# CHAT KEYS
# =========================================================

def _keys_of_chat(obj):
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


def _normalize_keys(keys):
    result = set()

    for key in keys or []:

        key = str(
            key or ""
        ).strip().lower()

        if not key:
            continue

        result.add(key)

        if key.startswith("@"):
            result.add(key[1:])
        else:
            result.add("@" + key)

    return result


def _chat_matches_keys(chat, keys):
    if not chat:
        return False

    possible = _keys_of_chat(chat)

    return bool(
        _normalize_keys(
            possible
        ).intersection(
            _normalize_keys(keys)
        )
    )


# =========================================================
# FIND LIVE CHANNEL
# =========================================================

def find_live_channel_by_keys(keys):

    if not keys:
        return None, None

    normalized_keys = _normalize_keys(
        keys
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

            possible = _normalize_keys(
                [channel_id]
            )

            if possible.intersection(
                normalized_keys
            ):

                return (
                    str(user_id),
                    channel,
                )

    return None, None


# =========================================================
# FIND CHANNEL BY CHAT OBJECT
# =========================================================

def find_live_channel_by_chat(chat):
    if not chat:
        return None, None

    return find_live_channel_by_keys(
        _keys_of_chat(chat)
    )


# =========================================================
# COMMENT UI
# =========================================================

def comment_text_view(channel):

    enabled = _is_comment_enabled(
        channel
    )

    text = (
        channel.get(
            "comment_text"
        )
        or ""
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
        "برای هر پست فقط یک کامنت ارسال می‌شود.\n"
        "کامنت به خود پست در بخش دیدگاه‌ها متصل می‌شود."
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

    user = get_user(
        user_id
    ) or {}

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
        payload[
            "comment_text"
        ] = str(
            text
        ).strip()[:400]

    if enabled is not None:
        payload[
            "comment_on"
        ] = bool(enabled)

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

async def on_callback(
    callback: CallbackQuery
):

    data = callback.data or ""

    user_id = callback.from_user.id

    user = (
        get_user(user_id)
        or {}
    )

    channels = (
        user.get("channels")
        or []
    )

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
                home_components(
                    user_id
                ),
            )

            return

        if not channels:

            await edit_message(
                callback,
                "📢 اول یک کانال ثبت کن.",
                home_components(
                    user_id
                ),
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

    if data.startswith(
        "cmtch_"
    ):

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

        fresh_user = (
            get_user(user_id)
            or {}
        )

        channel = find_channel(
            fresh_user,
            channel_id,
        )

        if not channel:
            return

        current_value = (
            _is_comment_enabled(
                channel
            )
        )

        new_value = (
            not current_value
        )

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

            await edit_message(
                callback,
                "❌ ذخیره وضعیت کامنت انجام نشد.",
                comment_menu(channel),
            )

            return

        await edit_message(
            callback,
            comment_text_view(
                updated
            ),
            comment_menu(
                updated
            ),
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
                state.get("data")
                or {}
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

        selected_text = (
            PRESETS[index]
        )

        channel = save_comment(
            user_id,
            channel_id,
            text=selected_text,
            enabled=True,
        )

        if not channel:
            return

        await edit_message(
            callback,
            "✅ متن ذخیره شد و کامنت روشن شد.\n\n"
            + comment_text_view(
                channel
            ),
            comment_menu(
                channel
            ),
        )

        return


# =========================================================
# CHANNEL POST
# =========================================================

def handle_channel_post(message):
    """
    فقط پست اصلی کانال trigger اولیه است.

    اینجا هنوز Reply نمی‌زنیم.

    ابتدا post_id و اطلاعات لازم را ذخیره می‌کنیم.
    سپس وقتی پیام همان پست در discussion group
    به شکل forward به بات رسید، آنجا Reply می‌زنیم.
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

    if chat_type != "channel":
        return False

    owner_id, channel = (
        find_live_channel_by_chat(
            chat
        )
    )

    if not channel:

        print(
            "⚠️ کانال در دیتابیس پیدا نشد | "
            f"keys={sorted(_keys_of_chat(chat))}"
        )

        return True

    channel_id = channel.get(
        "id"
    )

    if not _is_comment_enabled(
        channel
    ):

        print(
            f"🔴 کامنت خاموش است | "
            f"channel={channel_id}"
        )

        return True

    text = (
        channel.get(
            "comment_text"
        )
        or ""
    ).strip()

    if not text:

        print(
            f"⚠️ متن کامنت خالی است | "
            f"channel={channel_id}"
        )

        return True

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
            f"❌ ID پست کانال نامعتبر است | "
            f"channel={channel_id}"
        )

        return True

    group_id = get_linked_chat(
        channel_id
    )

    if not group_id:

        print(
            f"❌ گروه دیدگاه پیدا نشد | "
            f"channel={channel_id}"
        )

        return True

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    commented_posts = (
        channel.get(
            "commented_post_ids"
        )
        or []
    )

    try:
        commented_posts = [
            int(x)
            for x in commented_posts
        ]
    except Exception:
        commented_posts = []

    if message_id in commented_posts:

        print(
            f"🛑 این پست قبلاً کامنت شده | "
            f"channel={channel_id} | "
            f"post_id={message_id}"
        )

        return True

    # -----------------------------------------------------
    # PENDING
    # -----------------------------------------------------

    pending_channel = (
        _PENDING_POSTS
        .setdefault(
            str(channel_id),
            {},
        )
    )

    pending_channel[
        message_id
    ] = {
        "owner_id": owner_id,
        "channel_id": channel_id,
        "post_id": message_id,
        "group_id": str(group_id),
        "text": text,
        "created_at": time_now(),
    }

    print(
        f"📌 پست برای پیدا کردن پیام discussion "
        f"ثبت شد | "
        f"channel={channel_id} | "
        f"post_id={message_id} | "
        f"group={group_id}"
    )

    # -----------------------------------------------------
    # CLEAN OLD
    # -----------------------------------------------------

    cleanup_pending()

    return True


# =========================================================
# DISCUSSION MESSAGE
# =========================================================

def handle_discussion_message(
    message
):
    """
    پیام‌های گروه را بررسی می‌کند.

    فقط پیام خودکار پست کانال را قبول می‌کنیم.

    پیام کاربران عادی:
        هیچ کاری انجام نمی‌شود.

    پیام مربوط به پست کانال:
        post_id را از forward_from_message_id
        می‌گیریم و همان پیام گروه را Reply می‌کنیم.
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

    group_id = (
        getattr(
            chat,
            "id",
            None,
        )
        or getattr(
            chat,
            "chat_id",
            None,
        )
    )

    if group_id is None:
        return False

    group_id = str(
        group_id
    )

    # -----------------------------------------------------
    # ORIGINAL CHANNEL CHAT
    # -----------------------------------------------------

    forward_chat = getattr(
        message,
        "forward_from_chat",
        None,
    )

    forward_post_id = getattr(
        message,
        "forward_from_message_id",
        None,
    )

    # بعضی نسخه‌ها ممکن است مقدار را
    # به صورت string بدهند.
    if forward_post_id is None:

        raw_forward_id = getattr(
            message,
            "forward_from_message_id",
            None,
        )

        if raw_forward_id is not None:
            forward_post_id = raw_forward_id

    if forward_post_id is None:
        return False

    try:
        forward_post_id = int(
            forward_post_id
        )
    except Exception:
        return False

    # -----------------------------------------------------
    # FIND CHANNEL
    # -----------------------------------------------------

    owner_id, channel = (
        find_live_channel_by_chat(
            forward_chat
        )
    )

    if not channel:

        print(
            f"ℹ️ پیام گروه مربوط به کانال ثبت‌شده نیست | "
            f"group={group_id} | "
            f"forward_post={forward_post_id}"
        )

        return False

    channel_id = channel.get(
        "id"
    )

    # -----------------------------------------------------
    # CHECK GROUP
    # -----------------------------------------------------

    linked_group = get_linked_chat(
        channel_id
    )

    if not linked_group:
        return False

    if str(linked_group) != str(
        group_id
    ):

        print(
            f"⚠️ گروه پیام با گروه دیدگاه یکی نیست | "
            f"channel={channel_id} | "
            f"expected={linked_group} | "
            f"received={group_id}"
        )

        return False

    # -----------------------------------------------------
    # CHECK ENABLED
    # -----------------------------------------------------

    if not _is_comment_enabled(
        channel
    ):
        return False

    # -----------------------------------------------------
    # PENDING POST
    # -----------------------------------------------------

    pending_channel = (
        _PENDING_POSTS.get(
            str(channel_id)
        )
        or {}
    )

    pending = pending_channel.get(
        forward_post_id
    )

    if not pending:

        print(
            f"⚠️ پیام discussion پیدا شد ولی "
            f"پست در pending نیست | "
            f"channel={channel_id} | "
            f"post_id={forward_post_id}"
        )

        # اگر pending از بین رفته باشد،
        # با اطلاعات فعلی کانال هم می‌توانیم
        # در صورت وجود متن کامنت تلاش کنیم.
        text = (
            channel.get(
                "comment_text"
            )
            or ""
        ).strip()

        if not text:
            return False

    else:

        text = (
            pending.get(
                "text"
            )
            or ""
        ).strip()

    if not text:
        return False

    # -----------------------------------------------------
    # DISCUSSION MESSAGE ID
    # -----------------------------------------------------

    discussion_message_id = (
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
        discussion_message_id = int(
            discussion_message_id
        )
    except Exception:

        print(
            f"❌ ID پیام discussion نامعتبر است | "
            f"channel={channel_id} | "
            f"post_id={forward_post_id}"
        )

        return False

    # -----------------------------------------------------
    # DUPLICATE
    # -----------------------------------------------------

    commented_posts = (
        channel.get(
            "commented_post_ids"
        )
        or []
    )

    try:
        commented_posts = [
            int(x)
            for x in commented_posts
        ]
    except Exception:
        commented_posts = []

    if forward_post_id in commented_posts:

        print(
            f"🛑 کامنت قبلاً ارسال شده | "
            f"channel={channel_id} | "
            f"post_id={forward_post_id}"
        )

        pending_channel.pop(
            forward_post_id,
            None,
        )

        return True

    # -----------------------------------------------------
    # IN FLIGHT
    # -----------------------------------------------------

    flight_key = (
        f"{channel_id}:"
        f"{forward_post_id}"
    )

    if flight_key in _IN_FLIGHT:

        print(
            f"⏳ کامنت همین پست در حال ارسال است | "
            f"channel={channel_id} | "
            f"post_id={forward_post_id}"
        )

        return True

    _IN_FLIGHT.add(
        flight_key
    )

    try:

        print(
            f"🎯 پیام اصلی discussion پیدا شد | "
            f"channel={channel_id} | "
            f"channel_post={forward_post_id} | "
            f"discussion_message={discussion_message_id}"
        )

        # -------------------------------------------------
        # REAL REPLY
        # -------------------------------------------------

        result = send_discussion_reply(
            group_id,
            discussion_message_id,
            text,
        )

        if not isinstance(
            result,
            dict,
        ):
            print(
                f"❌ پاسخ API نامعتبر بود | "
                f"channel={channel_id}"
            )

            return True

        if not result.get("ok"):

            print(
                f"❌ کامنت ارسال نشد | "
                f"channel={channel_id} | "
                f"post_id={forward_post_id} | "
                f"description="
                f"{result.get('description', '')}"
            )

            return True

        # -------------------------------------------------
        # SAVE SUCCESS
        # -------------------------------------------------

        commented_posts.append(
            forward_post_id
        )

        # فقط آخرین 1000 پست نگه داشته شود
        commented_posts = (
            commented_posts[-1000:]
        )

        saved = _patch_channel(
            owner_id,
            channel_id,
            {
                "commented_post_ids":
                    commented_posts,

                "last_commented_post_id":
                    forward_post_id,
            },
        )

        print(
            f"✅ کامنت دقیقاً به پست discussion "
            f"Reply شد | "
            f"channel={channel_id} | "
            f"channel_post={forward_post_id} | "
            f"discussion_message={discussion_message_id} | "
            f"db_saved={saved}"
        )

        pending_channel.pop(
            forward_post_id,
            None,
        )

        return True

    finally:

        _IN_FLIGHT.discard(
            flight_key
        )


# =========================================================
# PRIVATE COMMENT TEXT
# =========================================================

async def handle_private_comment_text(
    message
):

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
        state.get("data")
        or {}
    ).get(
        "channel_id"
    )

    text = (
        message.content
        or ""
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
# TIME / CLEANUP
# =========================================================

def time_now():
    import time
    return time.time()


def cleanup_pending():
    now = time_now()

    for channel_id in list(
        _PENDING_POSTS.keys()
    ):

        posts = _PENDING_POSTS.get(
            channel_id
        )

        if not isinstance(
            posts,
            dict,
        ):
            _PENDING_POSTS.pop(
                channel_id,
                None,
            )
            continue

        for post_id in list(
            posts.keys()
        ):

            item = posts.get(
                post_id
            )

            if not isinstance(
                item,
                dict,
            ):
                posts.pop(
                    post_id,
                    None,
                )
                continue

            created_at = item.get(
                "created_at",
                now,
            )

            if now - created_at > 300:
                posts.pop(
                    post_id,
                    None,
                )

        if not posts:
            _PENDING_POSTS.pop(
                channel_id,
                None,
            )


# =========================================================
# MESSAGE EVENT
# =========================================================

async def on_message(
    message: Message
):

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
    # DISCUSSION GROUP
    # -----------------------------------------------------

    if chat_type in (
        "group",
        "supergroup",
    ):

        handle_discussion_message(
            message
        )

        return

    # -----------------------------------------------------
    # PRIVATE
    # -----------------------------------------------------

    await handle_private_comment_text(
        message
)
