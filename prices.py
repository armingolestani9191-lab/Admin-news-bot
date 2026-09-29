import time
from datetime import datetime

import requests

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = None


TGJU_URL = "https://call.tgju.org/ajax.json"
PRICE_CACHE_SECONDS = 30
_CACHE = {"at": 0, "current": {}}
HEADERS = {"User-Agent": "Mozilla/5.0 AutoNewsBot/2.7"}

WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

PRICE_GOLD = "طلا و ارز"
PRICE_CRYPTO = "ارز دیجیتال"
PRICE_CATEGORIES = (PRICE_GOLD, PRICE_CRYPTO)
OLD_ECONOMY = "اقتصاد"

GOLD_ITEMS = [
    ("💵", "دلار", "price_dollar_rl", "toman", 1),
    ("💵", "تتر", "crypto-tether-irr", "toman", 1),
    ("💶", "یورو", "price_eur", "toman", 1),
    ("💷", "پوند انگلستان", "price_gbp", "toman", 1),
    ("💵", "لیر ترکیه", "price_try", "toman", 1),
    ("💵", "درهم امارات", "price_aed", "toman", 1),
    ("💵", "یوآن چین", "price_cny", "toman", 1),
    ("💵", "۱۰۰ دینار عراق", "price_iqd", "toman", 100),
    ("💵", "افغانی افغانستان", "price_afn", "toman", 1),
    ("💵", "فرانک سوئیس", "price_chf", "toman", 1),
    ("💵", "دلار کانادا", "price_cad", "toman", 1),
    ("💵", "دلار استرالیا", "price_aud", "toman", 1),
    ("🌕", "اونس جهانی طلا", "ons", "usd", 1),
    ("🌕", "طلا ۱۸ عیار", "geram18", "toman", 1),
    ("🌕", "طلا ۲۴ عیار", "geram24", "toman", 1),
    ("🌕", "مثقال طلا", "mesghal", "toman", 1),
    ("🌕", "سکه امامی", "sekee", "toman", 1),
    ("🌕", "سکه بهار آزادی", "sekeb", "toman", 1),
    ("🌕", "نیم سکه", "nim", "toman", 1),
    ("🌕", "ربع سکه", "rob", "toman", 1),
]

CRYPTO_ITEMS = [
    ("₿", "بیت‌کوین", "crypto-bitcoin", "crypto-bitcoin-irr"),
    ("Ξ", "اتریوم", "crypto-ethereum", "crypto-ethereum-irr"),
    ("🟡", "بایننس‌کوین", "crypto-binance-coin", "crypto-binance-coin-irr"),
    ("◉", "سولانا", "crypto-solana", "crypto-solana-irr"),
    ("✕", "ریپل", "crypto-ripple", "crypto-ripple-irr"),
    ("🔵", "کاردانو", "crypto-cardano", "crypto-cardano-irr"),
    ("🐕", "دوج‌کوین", "crypto-dogecoin", "crypto-dogecoin-irr"),
    ("🔴", "ترون", "crypto-tron", "crypto-tron-irr"),
    ("🟢", "تون‌کوین", "crypto-toncoin", "crypto-toncoin-irr"),
    ("⛤", "اولنچ", "crypto-avalanche", "crypto-avalanche-irr"),
    ("◇", "پولکادات", "crypto-polkadot", "crypto-polkadot-irr"),
    ("🔗", "چین‌لینک", "crypto-chainlink", "crypto-chainlink-irr"),
    ("Ł", "لایت‌کوین", "crypto-litecoin", "crypto-litecoin-irr"),
    ("₿", "بیت‌کوین کش", "crypto-bitcoin-cash", "crypto-bitcoin-cash-irr"),
    ("⚛", "کاسموس", "crypto-cosmos", None),
    ("🤝", "یونی‌سوپ", "crypto-uniswap", None),
    ("🐾", "شیبا", "crypto-shiba-inu", "crypto-shiba-inu-irr"),
    ("✦", "استلار", "crypto-stellar", "crypto-stellar-irr"),
    ("🟦", "یو‌اس‌دی‌کوین", "crypto-usd-coin", "crypto-usd-coin-irr"),
    ("₮", "تتر", "crypto-tether", "crypto-tether-irr"),
]


def _now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)
    return datetime.now()


def _gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def iran_clock():
    now = _now_tehran()
    jy, jm, jd = _gregorian_to_jalali(now.year, now.month, now.day)
    weekday = WEEKDAYS[now.weekday()]
    month = MONTHS[jm - 1]
    clock = now.strftime("%H:%M")
    text = f"{weekday} {jd} {month} {jy} — {clock}"
    return text.translate(FA_DIGITS)


def _to_number(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace(",", "").replace("،", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_num(value, decimals=0):
    if value is None:
        return "—"
    if decimals:
        text = f"{value:,.{decimals}f}"
    else:
        text = f"{int(round(value)):,}"
    return text.replace(",", "٬").translate(FA_DIGITS)


def _node(current, key):
    item = current.get(key)
    return item if isinstance(item, dict) else None


def _rial_to_toman(value):
    if value is None:
        return None
    return value / 10.0


def fetch_current(force=False):
    now = time.time()
    if not force and _CACHE["current"] and now - _CACHE["at"] < PRICE_CACHE_SECONDS:
        return _CACHE["current"]
    try:
        response = requests.get(TGJU_URL, timeout=8, headers=HEADERS)
        payload = response.json() if response.status_code == 200 else {}
        current = payload.get("current") if isinstance(payload, dict) else {}
        if isinstance(current, dict) and current:
            _CACHE["current"] = current
            _CACHE["at"] = now
            return current
    except Exception as error:
        print("⚠️ خواندن قیمت موفق نبود:", error)
    return _CACHE["current"] or {}


def _gold_line(current, emoji, title, key, kind, multiply):
    node = _node(current, key)
    value = _to_number((node or {}).get("p"))
    if value is None:
        return f"{emoji} {title} = —"
    value *= multiply
    if kind == "usd":
        return f"{emoji} {title} = {_format_num(value, 2)} دلار"
    return f"{emoji} {title} = {_format_num(_rial_to_toman(value))} تومان"


def _crypto_line(current, emoji, title, usd_key, irr_key):
    usd = _to_number((_node(current, usd_key) or {}).get("p"))
    toman = None
    if irr_key:
        toman = _rial_to_toman(_to_number((_node(current, irr_key) or {}).get("p")))
    if usd is None and toman is None:
        return f"{emoji} {title} = —"
    decimals = 0 if usd is not None and usd >= 100 else (2 if usd is not None and usd >= 1 else 6)
    usd_text = _format_num(usd, decimals) if usd is not None else "—"
    if toman is not None:
        return f"{emoji} {title} = {usd_text} دلار | {_format_num(toman)} تومان"
    return f"{emoji} {title} = {usd_text} دلار"


def format_gold_board():
    current = fetch_current()
    lines = [
        "💰 قیمت لحظه‌ای دلار، طلا و سکه",
        f"⏰ {iran_clock()}",
    ]
    for item in GOLD_ITEMS:
        lines.append(_gold_line(current, *item))
    return "\n".join(lines)


def format_crypto_board():
    current = fetch_current()
    lines = [
        "💎 قیمت لحظه‌ای ارزهای دیجیتال",
        f"⏰ {iran_clock()}",
    ]
    for item in CRYPTO_ITEMS:
        lines.append(_crypto_line(current, *item))
    return "\n".join(lines)


def format_price_board(kind):
    if kind == PRICE_CRYPTO:
        return format_crypto_board()
    return format_gold_board()


def normalize_categories(categories):
    selected = []
    for item in categories or []:
        name = "طلا و ارز" if item == OLD_ECONOMY else item
        if name and name not in selected:
            selected.append(name)
    return selected or ["همه"]


def wants_price(categories, kind):
    selected = normalize_categories(categories)
    return kind in selected or "همه" in selected


def news_categories_only(categories):
    selected = normalize_categories(categories)
    if "همه" in selected:
        return ["همه"]
    return [name for name in selected if name not in PRICE_CATEGORIES]
