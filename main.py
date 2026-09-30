import time

from config import DEFAULT_SEND_INTERVAL, FORBIDDEN_COOLDOWN, MAX_NEWS_AGE_SECONDS, PREFER_NEWS_AGE_SECONDS
from rss_reader import get_news, is_fresh
from storage import is_news_sent, mark_news_sent
from users import get_user, update_last_send
from sender import send_message, send_photo
from utils import add_emoji
from category_engine import detect_category_advanced, news_matches_channel
from ai import translate_news
from analytics import record_message, snapshot_members
from commenter import extract_message_id, post_comment, remember_post
from news_targets import active_news_channels
from quiet_hours import is_24h, is_channel_open, news_after_wake, schedule_of
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
_QUIET_OPEN = {}
_QUIET_LOG = {}
_QUIET_SCHED = {}
_SEND_TURN = {}


def get_all_channels():
    return active_news_channels()


def needed_categories(channels):
    selected = set()
    for channel in channels:
        selected.update(news_categories_only(channel.get("categories") or ["همه"]))
    return list(selected)


def _same_channel(left, right):
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _schedule_key(channel):
    start, end = schedule_of(channel)
    return f"{start}|{end}"


def live_channel(channel):
    user_id = channel.get("user_id")
    channel_id = channel.get("id")
    if not user_id or not channel_id:
        return None
    try:
        user = get_user(user_id, force=True) or {}
    except Exception:
        return channel
    for item in user.get("channels") or []:
        if not _same_channel(item.get("id"), channel_id):
            continue
        if item.get("status") != "active":
            return None
        live = dict(item)
        live["user_id"] = user_id
        return live
    return None


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


def send_kinds_for(channel):
    categories = normalize_categories(channel.get("categories") or ["همه"])
    kinds = []
    if news_categories_only(categories):
        kinds.append("news")
    for kind in PRICE_CATEGORIES:
        if wants_price(categories, kind):
            kinds.append(kind)
    return kinds


def take_send_kind(channel, kinds):
    if not kinds:
        return None
    channel_id = str(channel["id"])
    try:
        turn = int(_SEND_TURN.get(channel_id, channel.get("send_turn") or 0))
    except (TypeError, ValueError):
        turn = 0
    kind = kinds[turn % len(kinds)]
    _SEND_TURN[channel_id] = turn + 1
    return kind


def remember_turn(channel):
    channel_id = str(channel["id"])
    turn = int(_SEND_TURN.get(channel_id) or 0)
    try:
        from users import _patch_channel
        _patch_channel(channel.get("user_id"), channel["id"], {"send_turn": turn})
    except Exception:
        pass


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
        if not news_after_wake(channel, item.get("published")):
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


def wake_if_needed(channel):
    channel_id = str(channel.get("id") or "")
    if not channel_id:
        return False
    key = _schedule_key(channel)
    prev = _QUIET_SCHED.get(channel_id)
    if prev is not None and prev != key:
        print(f"🔄 ساعت خاموشی {channel_id} عوض شد. از بازه جدید پیروی می‌شود.")
    _QUIET_SCHED[channel_id] = key
    if is_24h(channel):
        _QUIET_OPEN[channel_id] = True
        return True
    if not is_channel_open(channel):
        _QUIET_OPEN[channel_id] = False
        last = float(_QUIET_LOG.get(channel_id) or 0)
        if time.time() - last > 120:
            _QUIET_LOG[channel_id] = time.time()
            print(f"⏸️ کانال {channel_id} در زمان خاموشی است. هیچ خبر و قیمتی ارسال نمی‌شود.")
        return False
    if _QUIET_OPEN.get(channel_id) is False or (prev is not None and prev != key):
        now = time.time()
        channel["quiet_wake_at"] = now
        channel["last_send"] = 0
        try:
            from users import mark_quiet_wake
            mark_quiet_wake(channel.get("user_id"), channel["id"], now)
        except Exception:
            pass
        _PRICE_STATE[channel_id] = {}
        print(f"▶️ کانال {channel_id} دوباره روشن شد. فقط خبر جدید همین لحظه ارسال می‌شود.")
    _QUIET_OPEN[channel_id] = True
    return True


def finish_send(channel, result):
    if result.get("forbidden"):
        mark_forbidden(channel["id"])
        return False
    if not result.get("ok"):
        return False
    update_last_send(channel.get("user_id"), channel["id"], time.time())
    remember_turn(channel)
    try:
        record_message(channel["id"])
    except Exception:
        pass
    return True


def send_one_to_channel(channel, news_list):
    live = live_channel(channel)
    if not live or not wake_if_needed(live):
        return
    if not can_send(live):
        return
    kinds = send_kinds_for(live)
    if not kinds:
        return
    kind = take_send_kind(live, kinds)
    result = None
    latest_news = None
    if kind == "news":
        latest_news = pick_news_for_channel(live, news_list or [])
        if not latest_news:
            for other in kinds:
                if other == "news":
                    continue
                kind = other
                break
            else:
                return
    if kind != "news":
        live = live_channel(live)
        if not live or not wake_if_needed(live):
            return
        try:
            result = send_price_to_channel(live, kind)
        except Exception as error:
            print("❌ خطا در ارسال قیمت:", error)
            return
        if not isinstance(result, dict):
            result = {"ok": bool(result), "forbidden": False}
        if not finish_send(live, result):
            if result.get("forbidden"):
                return
            print(f"❌ لیست قیمت نرفت: {live['id']} {kind}")
            return
        remember_price(live, kind)
        print(f"✅ لیست {kind} برای {live['id']} ارسال شد")
        return
    live = live_channel(live)
    if not live or not wake_if_needed(live):
        return
    try:
        result = send_news_to_channel(live, latest_news)
    except Exception as send_error:
        print("❌ خطا در ارسال:", send_error)
        result = {"ok": False, "forbidden": False}
    if not isinstance(result, dict):
        result = {"ok": bool(result), "forbidden": False}
    if not finish_send(live, result):
        if result.get("forbidden"):
            return
        print(f"❌ ارسال ناموفق بود: {live['id']}")
        return
    mark_news_sent(live["id"], latest_news.get("link"))
    maybe_comment(live, result)
    age_min = max(0, int((time.time() - float(latest_news.get("published") or time.time())) // 60))
    categories = live.get("categories") or ["همه"]
    print(
        f"✅ ارسال شد به {live['id']}\n"
        f"🗂 دسته خبر: {latest_news.get('feed_category')}\n"
        f"🏷 فیلتر کانال: {', '.join(categories)}\n"
        f"⏱ عمر خبر: {age_min} دقیقه\n"
        f"⏰ ارسال بعدی: {DEFAULT_SEND_INTERVAL} دقیقه دیگر"
    )


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
            open_channels = []
            for channel in channels:
                live = live_channel(channel)
                if live and wake_if_needed(live):
                    open_channels.append(live)
            news_list = get_news(needed_categories(open_channels))
            for channel in open_channels:
                send_one_to_channel(channel, news_list)
            time.sleep(CHECK_INTERVAL)
        except Exception as error:
            print("❌ خطای اصلی:", error)
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
