from config import DEFAULT_SEND_INTERVAL
from users import load_users
from subscription import has_subscription, max_channels_for, is_free_user, FREE_ALLOWED_CATEGORIES


def active_news_channels():
    users = load_users()
    channels = []
    for user_id, user_data in users.items():
        if not isinstance(user_data, dict):
            continue
        if not has_subscription(user_id):
            continue
        limit = max_channels_for(user_id)
        owned = [item for item in (user_data.get("channels") or []) if isinstance(item, dict) and item.get("id")]
        for channel in owned[:limit]:
            if channel.get("status") != "active":
                continue
            item = dict(channel)
            item["user_id"] = user_id
            item.setdefault("interval", DEFAULT_SEND_INTERVAL)
            item.setdefault("last_send", 0)
            item.setdefault("categories", ["همه"])
            if is_free_user(user_id):
                allowed = list(FREE_ALLOWED_CATEGORIES)
                picked = [name for name in (item.get("categories") or []) if name in allowed]
                item["categories"] = picked or allowed
            item.setdefault("send_image", True)
            item.setdefault("show_emoji", True)
            item.setdefault("footer_text", "")
            item.setdefault("comment_on", False)
            item.setdefault("comment_text", "")
            channels.append(item)
    return channels
