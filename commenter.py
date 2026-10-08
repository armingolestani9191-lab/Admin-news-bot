import time
import requests

from config import BOT_TOKEN
from users import _patch_channel


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

_LINKED = {}


# =========================================================
# API
# =========================================================

def _call(method, payload):
    try:
        response = requests.post(
            f"{BASE_URL}/{method}",
            json=payload,
            timeout=10,
        )

        try:
            data = response.json()
        except ValueError:
            data = {
                "description": response.text[:500],
            }

        result = data.get("result")

        message_id = None

        if isinstance(result, dict):
            message_id = (
                result.get("message_id")
                or result.get("id")
            )

        elif isinstance(result, int):
            message_id = result

        try:
            if message_id is not None:
                message_id = int(message_id)
        except Exception:
            message_id = None

        ok = (
            bool(data.get("ok"))
            and response.status_code == 200
        )

        return {
            "ok": ok,
            "code": response.status_code,
            "description": str(
                data.get("description") or ""
            ),
            "message_id": message_id,
            "raw": data,
        }

    except Exception as error:
        return {
            "ok": False,
            "code": 0,
            "description": str(error),
            "message_id": None,
            "raw": {},
        }


# =========================================================
# MESSAGE ID
# =========================================================

def extract_message_id(result):
    if not isinstance(result, dict):
        return None

    message_id = result.get("message_id")

    if message_id is not None:
        try:
            return int(message_id)
        except Exception:
            pass

    raw = result.get("raw") or {}

    body = (
        raw.get("result")
        if isinstance(raw, dict)
        else None
    )

    if isinstance(body, dict):
        message_id = (
            body.get("message_id")
            or body.get("id")
        )

        try:
            if message_id is not None:
                return int(message_id)
        except Exception:
            pass

    return None


# =========================================================
# LINKED DISCUSSION CHAT
# =========================================================

def get_linked_chat(channel_id):
    """
    پیدا کردن گروه دیدگاه متصل به کانال.
    """

    if not channel_id:
        return None

    cache_key = str(channel_id)

    cached = _LINKED.get(cache_key)

    if cached:
        saved_time, saved_group = cached

        if time.time() - saved_time < 180:
            return saved_group

    result = _call(
        "getChat",
        {
            "chat_id": channel_id,
        },
    )

    raw = result.get("raw") or {}

    chat = (
        raw.get("result")
        if isinstance(raw, dict)
        else None
    )

    if not isinstance(chat, dict):
        chat = {}

    linked = (
        chat.get("linked_chat_id")
        or chat.get("linked_chat")
        or chat.get("discussion_chat_id")
    )

    if isinstance(linked, dict):
        linked = (
            linked.get("id")
            or linked.get("chat_id")
        )

    if linked is not None:
        linked = str(linked)

    _LINKED[cache_key] = (
        time.time(),
        linked,
    )

    if linked:
        print(
            f"🔗 گروه دیدگاه کانال "
            f"{channel_id}: {linked}"
        )
    else:
        print(
            f"⚠️ گروه دیدگاه کانال "
            f"{channel_id} پیدا نشد | "
            f"{result.get('description', '')}"
        )

    return linked


# =========================================================
# SEND REPLY
# =========================================================

def send_discussion_reply(
    group_id,
    discussion_message_id,
    text,
):
    """
    ارسال کامنت به عنوان Reply به پیام پست
    داخل گروه دیدگاه.

    خیلی مهم:
    discussion_message_id باید ID پیام داخل
    گروه دیدگاه باشد، نه ID پست کانال.
    """

    if not group_id:
        return {
            "ok": False,
            "description": "missing-group-id",
        }

    if discussion_message_id is None:
        return {
            "ok": False,
            "description": "missing-discussion-message-id",
        }

    text = (text or "").strip()

    if not text:
        return {
            "ok": False,
            "description": "empty-text",
        }

    try:
        discussion_message_id = int(
            discussion_message_id
        )
    except Exception:
        return {
            "ok": False,
            "description": "invalid-discussion-message-id",
        }

    payload = {
        "chat_id": group_id,
        "text": text,
        "reply_to_message_id": discussion_message_id,
    }

    print(
        f"📤 ارسال Reply کامنت | "
        f"group={group_id} | "
        f"discussion_message_id={discussion_message_id} | "
        f"text={text!r}"
    )

    result = _call(
        "sendMessage",
        payload,
    )

    if result.get("ok"):
        print(
            f"✅ Reply کامنت ارسال شد | "
            f"group={group_id} | "
            f"reply_to={discussion_message_id} | "
            f"message_id={result.get('message_id')}"
        )
    else:
        print(
            f"❌ Reply کامنت ارسال نشد | "
            f"group={group_id} | "
            f"reply_to={discussion_message_id} | "
            f"code={result.get('code')} | "
            f"{result.get('description', '')}"
        )

    return result


# =========================================================
# OLD COMPATIBILITY FUNCTION
# =========================================================

def _send_to_group(
    group_id,
    text,
    reply_to_message_id=None,
):
    """
    برای سازگاری با کدهای قبلی نگه داشته شده.
    """

    return send_discussion_reply(
        group_id,
        reply_to_message_id,
        text,
    )


# =========================================================
# POST COMMENT
# =========================================================

def post_comment(
    channel_id,
    text,
    reply_to=None,
    group_message_id=None,
    group_id=None,
):
    """
    ارسال کامنت.

    reply_to / group_message_id باید ID پیام پست
    داخل گروه دیدگاه باشد.

    هرگز ID مستقیم پست کانال را به عنوان
    reply_to استفاده نمی‌کنیم.
    """

    text = (text or "").strip()

    if not text:
        return {
            "ok": False,
            "description": "empty-text",
        }

    target_group = group_id

    if not target_group:
        target_group = get_linked_chat(
            channel_id
        )

    if not target_group:
        print(
            f"❌ گروه دیدگاه برای کانال "
            f"{channel_id} پیدا نشد."
        )

        return {
            "ok": False,
            "description": "no-linked-group",
        }

    discussion_message_id = reply_to

    if discussion_message_id is None:
        discussion_message_id = group_message_id

    if discussion_message_id is None:
        print(
            f"❌ ID پیام پست داخل گروه دیدگاه وجود ندارد | "
            f"channel={channel_id}"
        )

        return {
            "ok": False,
            "description": "missing-discussion-message-id",
        }

    return send_discussion_reply(
        target_group,
        discussion_message_id,
        text,
    )


# =========================================================
# REMEMBER POST
# =========================================================

def remember_post(
    user_id,
    channel_id,
    message_id,
):
    """
    ذخیره آخرین پست ارسال‌شده.
    """

    if not user_id:
        return

    if not channel_id:
        return

    if not message_id:
        return

    try:
        _patch_channel(
            user_id,
            channel_id,
            {
                "last_post_id": int(
                    message_id
                ),
            },
        )
    except Exception:
        pass
