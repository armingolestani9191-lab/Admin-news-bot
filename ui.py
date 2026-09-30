import threading

import requests

from config import BOT_TOKEN


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
_SESSION = requests.Session()


def _callback_id(target):
    for name in ("callback_id", "query_id", "id"):
        value = getattr(target, name, None)
        if value:
            return str(value)
    message = getattr(target, "message", None)
    if message is not None:
        for name in ("callback_id", "query_id"):
            value = getattr(message, name, None)
            if value:
                return str(value)
    return None


def _send_answer(query_id):
    try:
        _SESSION.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": query_id},
            timeout=1.0,
        )
    except Exception:
        pass


def answer_callback(target):
    if getattr(target, "_answered", False):
        return True
    query_id = _callback_id(target)
    if not query_id:
        return False
    try:
        target._answered = True
    except Exception:
        pass
    try:
        threading.Thread(target=_send_answer, args=(query_id,), daemon=True).start()
        return True
    except Exception:
        _send_answer(query_id)
        return True


async def edit_message(target, text, components=None):
    answer_callback(target)
    message = getattr(target, "message", target)
    try:
        if components is None:
            await message.edit(text)
        else:
            await message.edit(text, components=components)
        return True
    except Exception as error:
        text_error = str(error).lower()
        if "not modified" in text_error or "message is not modified" in text_error:
            return True
        try:
            if components is None:
                await message.reply(text)
            else:
                await message.reply(text, components=components)
        except Exception:
            return False
        return False
