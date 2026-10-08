import time

import requests

from config import BOT_TOKEN
from users import _patch_channel


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

_LINKED = {}


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


def extract_message_id(result):
    if not isinstance(result, dict):
        return None

    message_id = result.get("message_id")

    if message_id:
        try:
            return int(message_id)
        except Exception:
            return None

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
            return int(message_id) if message_id else None
        except Exception:
            return None

    return None


def get_linked_chat(channel_id):
    """
    پیدا کردن گروه دیدگاه متصل به کانال.
    نتیجه برای مدت کوتاه cache می‌شود.
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


def _send_to_group(
    group_id,
    text,
    reply_to_message_id=None,
):
    """
    ارسال کامنت به گروه دیدگاه.

    اگر reply_to_message_id وجود داشته باشد،
    پیام دقیقاً به همان پیام Reply می‌شود.

    در سیستم کامنت ما این ID همان message_id
    پست کانال است.
    """

    if not group_id:
        return {
            "ok": False,
            "description": "missing-group-id",
        }

    text = (text or "").strip()

    if not text:
        return {
            "ok": False,
            "description": "empty-text",
        }

    payload = {
        "chat_id": group_id,
        "text": text,
    }

    if reply_to_message_id is not None:
        try:
            reply_to_message_id = int(
                reply_to_message_id
            )

            payload[
                "reply_to_message_id"
            ] = reply_to_message_id

        except Exception:
            print(
                f"⚠️ reply_to_message_id نامعتبر بود | "
                f"value={reply_to_message_id!r}"
            )

    print(
        f"📤 ارسال کامنت | "
        f"group_id={group_id} | "
        f"reply_to={payload.get('reply_to_message_id')} | "
        f"text={text!r}"
    )

    result = _call(
        "sendMessage",
        payload,
    )

    if result.get("ok"):
        print(
            f"✅ کامنت با موفقیت ارسال شد | "
            f"group_id={group_id} | "
            f"reply_to={payload.get('reply_to_message_id')} | "
            f"message_id={result.get('message_id')}"
        )
    else:
        print(
            f"❌ ارسال کامنت ناموفق بود | "
            f"group_id={group_id} | "
            f"reply_to={payload.get('reply_to_message_id')} | "
            f"code={result.get('code')} | "
            f"{result.get('description', '')}"
        )

    return result


def post_comment(
    channel_id,
    text,
    reply_to=None,
    group_message_id=None,
    group_id=None,
):
    """
    ارسال کامنت برای پست کانال.

    reply_to:
        message_id پست کانال.

    group_message_id:
        برای سازگاری با نسخه‌های قبلی نگه داشته شده.

    فقط reply_to استفاده می‌شود.
    پیام‌های کاربران گروه هیچ نقشی ندارند.
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

    # مهم:
    # reply_to همان message_id پست کانال است.
    reply_message_id = reply_to

    if reply_message_id is None:
        reply_message_id = group_message_id

    if reply_message_id is None:
        print(
            f"❌ message_id پست برای Reply وجود ندارد | "
            f"channel={channel_id}"
        )

        return {
            "ok": False,
            "description": "missing-reply-message-id",
        }

    result = _send_to_group(
        target_group,
        text,
        reply_to_message_id=reply_message_id,
    )

    if result.get("ok"):
        print(
            f"💬 کامنت Reply شد | "
            f"channel={channel_id} | "
            f"reply_to={reply_message_id}"
        )

        return result

    print(
        f"⚠️ کامنت کانال ارسال نشد | "
        f"channel={channel_id}"
    )

    return result


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
