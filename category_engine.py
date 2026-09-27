from urllib.parse import urlparse

from config import CATEGORY_RULES, IRAN_HINTS


def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return " ".join(text.split())


def source_host(source):
    if not isinstance(source, str):
        return ""
    source = source.strip().lower()
    if "://" not in source:
        return source
    try:
        return urlparse(source).netloc.replace("www.", "")
    except Exception:
        return source


def score_category(title, source, rules):
    text = normalize_text(title)
    host = source_host(source)
    raw_source = normalize_text(source)
    score = 0
    for word in rules.get("keywords", []):
        word = normalize_text(word)
        if word and word in text:
            score += 3
    for word in rules.get("negative", []):
        word = normalize_text(word)
        if word and word in text:
            score -= 6
    for site in rules.get("sources", []):
        site = normalize_text(site)
        if site and (site in host or site in raw_source):
            score += 8
    if rules.get("require_iran"):
        if not any(normalize_text(word) in text for word in IRAN_HINTS):
            score -= 4
    return score


def _looks_like_weather(title):
    text = normalize_text(title)
    words = CATEGORY_RULES.get("آب‌وهوا", {}).get("keywords", [])
    return any(normalize_text(word) and normalize_text(word) in text for word in words)


def news_matches_channel(title, source, selected_categories, feed_category=None):
    selected = [item for item in (selected_categories or []) if item]
    if not selected:
        return False
    if "همه" in selected:
        if feed_category == "آب‌وهوا" and not _looks_like_weather(title):
            return False
        return True
    if feed_category and feed_category in selected:
        if feed_category == "آب‌وهوا":
            return _looks_like_weather(title)
        return True
    guessed = None
    best = 0
    for name, rules in CATEGORY_RULES.items():
        score = score_category(title, source, rules)
        if score > best:
            best = score
            guessed = name
    return bool(guessed and guessed in selected and best >= 3)


def detect_categories(title, source="", feed_category=None):
    if feed_category:
        return [feed_category]
    best_name = None
    best_score = 0
    for name, rules in CATEGORY_RULES.items():
        score = score_category(title, source, rules)
        if score > best_score:
            best_score = score
            best_name = name
    if best_name and best_score >= 3:
        return [best_name]
    return []


def detect_category_advanced(title, source="", feed_category=None):
    matched = detect_categories(title, source, feed_category)
    return matched[0] if matched else (feed_category or "عمومی")
