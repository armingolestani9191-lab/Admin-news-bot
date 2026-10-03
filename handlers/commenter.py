import time
import requests
from config import BOT_TOKEN

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
_LINKED = {}

def _call(method, payload):
    try:
        response = requests.post(f"{BASE_URL}/{method}", json=payload, timeout=10)
        data = response.json() if response.content else {"ok": False}
        result = data.get("result") or {}
        message_id = result.get("message_id") if isinstance(result, dict) else None
        return {"ok": data.get("ok", False), "message_id": int(message_id) if message_id else None}
    except:
        return {"ok": False}

def get_linked_chat(channel_id):
    if channel_id in _LINKED and time.time() - _LINKED[channel_id][0] < 180:
        return _LINKED[channel_id][1]
    data = _call("getChat", {"chat_id": channel_id})
    result = data.get("result") or {}
    linked = result.get("discussion_chat_id") or result.get("linked_chat_id") or result.get("linked_chat")
    if isinstance(linked, dict):
        linked = linked.get("id") or linked.get("chat_id")
    _LINKED[channel_id] = (time.time(), linked)
    return linked

def post_comment(channel_id: int, text: str, reply_to: int = None):
    if not text.strip():
        return
    group_id = get_linked_chat(channel_id)
    if not group_id:
        return
    payload = {"chat_id": group_id, "text": text}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    _call("sendMessage", payload)
