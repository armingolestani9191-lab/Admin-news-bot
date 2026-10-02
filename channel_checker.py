import requests

from config import BOT_TOKEN


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

_SESSION = requests.Session()

_SESSION.headers.update({
    "Content-Type": "application/json"
})


def get_chat_member(chat_id, user_id):
    """
    بررسی وضعیت عضویت کاربر در کانال/گروه.

    خروجی:
        creator
        administrator
        member
        restricted
        left
        kicked
        None -> خطا در ارتباط یا پاسخ نامعتبر
    """

    if chat_id is None or user_id is None:
        return None

    try:
        user_id = int(user_id)
    except Exception:
        return None

    chat_id = str(chat_id).strip()

    if not chat_id:
        return None

    try:
        response = _SESSION.post(
            f"{BASE_URL}/getChatMember",
            json={
                "chat_id": chat_id,
                "user_id": user_id,
            },
            timeout=3,
        )

        if response.status_code != 200:
            print(
                "getChatMember HTTP error:",
                response.status_code,
            )
            return None

        try:
            data = response.json()
        except Exception:
            print(
                "getChatMember invalid JSON"
            )
            return None

        if not isinstance(data, dict):
            return None

        if not data.get("ok"):
            return None

        result = data.get("result")

        if not isinstance(result, dict):
            return None

        status = result.get("status")

        if status is None:
            return None

        return str(status).strip().lower()

    except requests.Timeout:
        print(
            "getChatMember timeout:",
            chat_id,
        )
        return None

    except requests.RequestException as error:
        print(
            "getChatMember request error:",
            error,
        )
        return None

    except Exception as error:
        print(
            "getChatMember error:",
            error,
        )
        return None
