import requests

from config import BOT_TOKEN


BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"


def _callback_id(target):
    for name in ("id", "callback_id", "query_id"):
        value = getattr(target, name, None)
        if value:
            return str(value)
    return None


def answer_callback(target):
    query_id = _callback_id(target)
    if not query_id:
        return False
    try:
        requests.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": query_id},
            timeout=2,
        )
        return True
    except Exception:
        return False


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
