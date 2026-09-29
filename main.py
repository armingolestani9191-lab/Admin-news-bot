import time

from config import DEFAULT_SEND_INTERVAL, FORBIDDEN_COOLDOWN, MAX_NEWS_AGE_SECONDS, PREFER_NEWS_AGE_SECONDS
from rss_reader import get_news, is_fresh
from storage import is_news_sent, mark_news_sent
from users import update_last_send
from sender import send_message, send_photo
from utils import add_emoji
from category_engine import detect_category_advanced, news_matches_channel
from ai import translate_news
from analytics import record_message, snapshot_members
from commenter import extract_message_id, post_comment, remember_post
from news_targets import active_news_channels
from prices import (
    PRICE_CATEGORIES,
    fetch_current,
    format_price_board,
    news_categories_only,
    normalize_categories,
    wants_price,
)


CHECK_INTERVAL = 10
_FORBIDDEN_UNTIL = {}
_LAST_EMPTY = 0
_LAST_SNAP = 0
_PRICE_STATE = {}


def get_all_channels():
    return active_news_channels()


def needed_categories(channels):
    selected = set()
    for channel in channels:
        selected.update(news_categories_only(channel.get("categories") or ["همه"]))
    return list(selected)


def build_message(news, channel):
    title = (news.get("title") or "").strip()
    try:
        title = translate_news(title)
    except Exception:
        pass
    category = news.get("feed_category") or detect_category_advanced(
        title, news.get("source", ""), news.get("feed_category")
    )
    if channel.get("show_emoji", True):
        title = add_emoji(title, category)
    message = title
    footer = (channel.get("footer_text") or "").strip()
    if footer:
        message += f"\n\n{footer}"
    return message


def can_send(channel):
    channel_id = channel["id"]
    until = _FORBIDDEN_UNTIL.get(channel_id, 0)
    if until > time.time():
        return False
    now = time.time()
    last_send = float(channel.get("last_send") or 0)
    wait_minutes = max(1, int(DEFAULT_SEND_INTERVAL or 1))
    return (now - last_send) >= wait_minutes * 60


def _price_wait_seconds(channel):
    minutes = int(channel.get("interval") or DEFAULT_SEND_INTERVAL or 1)
    return max(30, minutes * 60)


def can_send_price(channel, kind):
    channel_id = str(channel["id"])
    until = _FORBIDDEN_UNTIL.get(channel["id"], 0)
    if until > time.time():
        return False
    state = _PRICE_STATE.get(channel_id, {}).get(kind) or {}
    last = float(state.get("at") or channel.get(f"price_at_{kind}") or 0)
    return (time.time() - last) >= _price_wait_seconds(channel)


def remember_price(channel, kind):
    channel_id = str(channel["id"])
    bucket = _PRICE_STATE.setdefault(channel_id, {})
    bucket[kind] = {"at": time.time()}
    try:
        from users import _patch_channel
        _patch_channel(channel.get("user_id"), channel["id"], {
            f"price_at_{kind}": time.time(),
        })
    except Exception:
        pass


def send_price_to_channel(channel, kind):
    fetch_current(force=True)
    text = format_price_board(kind)
    footer = (channel.get("footer_text") or "").strip()
    if footer:
        text += f"\n\n{footer}"
    return send_message(channel["id"], text)


def pick_news_for_channel(channel, news_list):
    categories = news_categories_only(channel.get("categories") or ["همه"])
    if not categories:
        return None
    unused = []
    for item in news_list:
        link = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        if not link or not title:
            continue
        if not is_fresh(item, max_age=MAX_NEWS_AGE_SECONDS):
            continue
        if is_news_sent(channel["id"], link):
            continue
        if not news_matches_channel(
            title,
            item.get("source", ""),
            categories,
            item.get("feed_category"),
        ):
            continue
        unused.append(item)
    if not unused:
        return None
    prefer = [item for item in unused if is_fresh(item, max_age=PREFER_NEWS_AGE_SECONDS)]
    pool = prefer or unused
    pool.sort(key=lambda item: item.get("published") or 0, reverse=True)
    return pool[0]


def send_news_to_channel(channel, news):
    message = build_message(news, channel)
    image = news.get("image")
    if channel.get("send_image", True) and image:
        return send_photo(channel["id"], image, message)
    return send_message(channel["id"], message)


def maybe_comment(channel, result):
    if not channel.get("comment_on"):
        return
    text = (channel.get("comment_text") or "").strip()
    if not text:
        return
    message_id = extract_message_id(result)
    remember_post(channel.get("user_id"), channel["id"], message_id)
    time.sleep(0.4)
    comment = post_comment(channel["id"], text, message_id)
    if not comment.get("ok"):
        print(f"⚠️ کامنت {channel['id']} نرفت: {comment.get('description', '')[:120]}")


def mark_forbidden(channel_id):
    _FORBIDDEN_UNTIL[channel_id] = time.time() + FORBIDDEN_COOLDOWN
    print(f"⏰ {channel_id} به خاطر 403 برای {FORBIDDEN_COOLDOWN // 60} دقیقه نادیده شد.")


def handle_prices(channel):
    categories = normalize_categories(channel.get("categories") or ["همه"])
    for kind in PRICE_CATEGORIES:
        if not wants_price(categories, kind):
            continue
        if not can_send_price(channel, kind):
            continue
        try:
            result = send_price_to_channel(channel, kind)
        except Exception as error:
            print("❌ خطا در ارسال قیمت:", error)
            continue
        if result.get("forbidden"):
            mark_forbidden(channel["id"])
            return
        if not result.get("ok"):
            print(f"❌ لیست قیمت نرفت: {channel['id']} {kind}")
            continue
        remember_price(channel, kind)
        try:
            record_message(channel["id"])
        except Exception:
            pass
        print(f"✅ لیست {kind} برای {channel['id']} ارسال شد")


def run():
    global _LAST_EMPTY, _LAST_SNAP
    print("🚀 AutoNewsBot MultiChannel Started...")
    while True:
        try:
            channels = get_all_channels()
            if not channels:
                now = time.time()
                if now - _LAST_EMPTY > 120:
                    print("ℹ️ کانال فعالی برای ارسال نیست")
                    _LAST_EMPTY = now
                time.sleep(CHECK_INTERVAL)
                continue
            now = time.time()
            if now - _LAST_SNAP > 600:
                for channel in channels:
                    try:
                        snapshot_members(channel["id"])
                    except Exception:
                        pass
                _LAST_SNAP = now
            for channel in channels:
                handle_prices(channel)
            news_list = get_news(needed_categories(channels))
            for channel in channels:
                if not can_send(channel):
                    continue
                latest_news = pick_news_for_channel(channel, news_list or [])
                if not latest_news:
                    continue
                try:
                    result = send_news_to_channel(channel, latest_news)
                except Exception as send_error:
                    print("❌ خطا در ارسال:", send_error)
                    result = {"ok": False, "forbidden": False}
                if not isinstance(result, dict):
                    result = {"ok": bool(result), "forbidden": False}
                if result.get("forbidden"):
                    mark_forbidden(channel["id"])
                    continue
                if not result.get("ok"):
                    print(f"❌ ارسال ناموفق بود: {channel['id']}")
                    continue
                mark_news_sent(channel["id"], latest_news.get("link"))
                update_last_send(channel["user_id"], channel["id"], time.time())
                maybe_comment(channel, result)
                try:
                    record_message(channel["id"])
                except Exception:
                    pass
                age_min = max(0, int((time.time() - float(latest_news.get("published") or time.time())) // 60))
                categories = channel.get("categories") or ["همه"]
                print(
                    f"✅ ارسال شد به {channel['id']}\n"
                    f"🗂 دسته خبر: {latest_news.get('feed_category')}\n"
                    f"🏷 فیلتر کانال: {', '.join(categories)}\n"
                    f"⏱ عمر خبر: {age_min} دقیقه\n"
                    f"⏰ ارسال بعدی: {DEFAULT_SEND_INTERVAL} دقیقه دیگر"
                )
            time.sleep(CHECK_INTERVAL)
        except Exception as error:
            print("❌ خطای اصلی:", error)
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
