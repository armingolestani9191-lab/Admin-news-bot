# ==========================
# AutoNewsBot Config v3.0
# SQLite Storage Edition
# ==========================

import os


# ==========================
# Bot
# ==========================

# 🟢 توکن بات را فقط بین کوتیشن‌های پایین قرار بده
BOT_TOKEN = "1484088959:653ntnnmPdDkkjwfI7IvZITjxNZ1bSwbnpw"


# ==========================
# Permanent Admins
# ==========================

# 🟢 ادمین اصلی و دائمی
# این ادمین به SQLite وابسته نیست.
# حتی اگر دیتابیس پاک شود، این ID همچنان ادمین باقی می‌ماند.

ADMIN_IDS = [
    595450272,
]


# ==========================
# SQLite Database
# ==========================

if os.getenv("DATABASE_PATH"):
    DATABASE_PATH = os.getenv("DATABASE_PATH")

elif os.path.isdir("/data"):
    DATABASE_PATH = "/data/admin_news.db"

else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "data", "admin_news.db")


# ==========================
# General Settings
# ==========================

MAX_SENT_NEWS = 5000

CHECK_EMPTY_INTERVAL = 60

SEND_INTERVALS = [
    60,
    300,
    600,
]

MAX_CHANNELS = 3

RSS_CACHE_SECONDS = 20

FORBIDDEN_COOLDOWN = 1800

DEFAULT_SEND_INTERVAL = 1

PREFER_NEWS_AGE_SECONDS = 8 * 60

MAX_NEWS_AGE_SECONDS = 30 * 60

FALLBACK_NEWS_AGE_SECONDS = 30 * 60


# ==========================
# RSS Sources
# ==========================

CATEGORY_FEEDS = {

    "ورزش": [
        "https://www.mehrnews.com/rss/tp/9",
        "https://www.isna.ir/rss/tp/24",
        "https://www.isna.ir/rss/tp/119",
        "https://www.varzesh3.com/rss/all",
    ],

    "جنگ": [
        "https://defapress.ir/fa/rss/38",
        "https://www.mehrnews.com/rss/tp/39",
        "https://www.isna.ir/rss/tp/407",
        "https://www.irna.ir/rss/tp/9",
        "https://www.imna.ir/rss/tp/144",
    ],

    "آب‌وهوا": [
        "https://www.isna.ir/rss/tp/62",
        "https://www.imna.ir/rss/tp/153",
        "https://www.irna.ir/rss/tp/12",
    ],

    "اقتصاد": [
        "https://www.sena.ir/rss",
        "https://www.mehrnews.com/rss/tp/20",
        "https://www.irna.ir/rss/tp/20",
        "https://www.isna.ir/rss/tp/34",
    ],

    "فناوری": [
        "https://www.zoomit.ir/feed/",
        "https://www.isna.ir/rss/tp/41",
        "https://digiato.com/feed",
    ],

    "سیاسی": [
        "https://www.mehrnews.com/rss/tp/7",
        "https://www.isna.ir/rss/tp/14",
        "https://www.irna.ir/rss/tp/5",
    ],
}


# ==========================
# All RSS Feeds
# ==========================

RSS_FEEDS = []

for _feeds in CATEGORY_FEEDS.values():

    for _url in _feeds:

        if _url not in RSS_FEEDS:
            RSS_FEEDS.append(_url)


# ==========================
# Category Rules
# ==========================

CATEGORY_RULES = {

    "ورزش": {

        "sources": [
            "mehrnews.com/rss/tp/9",
            "isna.ir/rss/tp/24",
            "isna.ir/rss/tp/119",
            "varzesh3.com",
        ],

        "keywords": [
            "فوتبال",
            "والیبال",
            "بسکتبال",
            "لیگ برتر",
            "لیگ",
            "جام جهانی",
            "بازیکن",
            "مربی",
            "قهرمانی",
            "استقلال",
            "پرسپولیس",
            "ورزش",
            "تیم ملی",
            "داور",
            "گل",
            "مسابقه ورزشی",
        ],

        "negative": [
            "موشک",
            "پهپاد",
            "هواشناسی",
            "بارش باران",
            "غزه",
            "حمله نظامی",
        ],
    },


    "اقتصاد": {

        "sources": [
            "sena.ir",
            "mehrnews.com/rss/tp/20",
            "irna.ir/rss/tp/20",
            "isna.ir/rss/tp/34",
        ],

        "keywords": [
            "دلار",
            "طلا",
            "سکه",
            "بورس",
            "ارز",
            "اقتصاد",
            "تورم",
            "نرخ ارز",
            "بانک مرکزی",
            "نفت",
            "بازار سرمایه",
        ],

        "negative": [
            "فوتبال",
            "هواشناسی",
            "جنگنده",
            "غزه",
        ],
    },


    "جنگ": {

        "sources": [
            "defapress.ir",
            "mehrnews.com/rss/tp/39",
            "isna.ir/rss/tp/407",
            "irna.ir/rss/tp/9",
            "imna.ir/rss/tp/144",
        ],

        "keywords": [
            "جنگ",
            "حمله نظامی",
            "حمله موشکی",
            "موشک",
            "پهپاد",
            "ارتش",
            "عملیات نظامی",
            "درگیری مسلحانه",
            "جنگنده",
            "تجاوز نظامی",
            "شهادت",
            "بمباران",
            "پدافند",
            "غزه",
            "لبنان",
            "سپاه",
            "حماس",
            "حزب الله",
            "اسرائیل",
            "مقاومت",
            "راکت",
            "انفجار",
            "نظامی",
        ],

        "negative": [
            "هواشناسی",
            "بارش باران",
            "فوتبال",
            "لیگ برتر",
            "استقلال",
            "پرسپولیس",
            "دلار",
            "بورس",
        ],
    },


    "فناوری": {

        "sources": [
            "zoomit.ir",
            "isna.ir/rss/tp/41",
            "digiato.com",
        ],

        "keywords": [
            "گوشی",
            "موبایل",
            "لپ تاپ",
            "هوش مصنوعی",
            "تکنولوژی",
            "اینترنت",
            "نرم افزار",
            "اپلیکیشن",
            "فناوری",
        ],

        "negative": [
            "موشک",
            "فوتبال",
            "غزه",
        ],
    },


    "سیاسی": {

        "sources": [
            "mehrnews.com/rss/tp/7",
            "isna.ir/rss/tp/14",
            "irna.ir/rss/tp/5",
        ],

        "keywords": [
            "مجلس",
            "دولت",
            "وزیر",
            "هیئت دولت",
            "رئیس جمهور",
            "انتخابات",
            "نماینده مجلس",
            "سیاست خارجی",
        ],

        "negative": [
            "فوتبال",
            "هواشناسی",
            "موشک",
            "پهپاد",
        ],
    },


    "آب‌وهوا": {

        "sources": [
            "isna.ir/rss/tp/62",
            "imna.ir/rss/tp/153",
            "irna.ir/rss/tp/12",
        ],

        "keywords": [
            "هواشناسی",
            "پیش بینی هوا",
            "پیش‌بینی هوا",
            "وضعیت هوا",
            "بارش باران",
            "بارش برف",
            "سامانه بارشی",
            "هشدار هواشناسی",
            "هشدار زرد",
            "هشدار نارنجی",
            "هشدار قرمز",
            "وزش باد شدید",
            "کاهش دما",
            "افزایش دما",
            "گرد و غبار",
            "آلودگی هوا",
            "رگبار",
            "تگرگ",
            "طوفان",
            "سیلاب",
        ],

        "negative": [
            "موشک",
            "پهپاد",
            "فوتبال",
            "دلار",
            "بورس",
            "غزه",
        ],

        "require_iran": True,
    },
}


# ==========================
# Iran Weather Hints
# ==========================

IRAN_HINTS = [
    "ایران",
    "کشور",
    "استان",
    "تهران",
    "مشهد",
    "اصفهان",
    "شیراز",
    "تبریز",
    "اهواز",
    "کرج",
    "قم",
    "کرمان",
    "گیلان",
    "مازندران",
    "آذربایجان",
    "خراسان",
    "خوزستان",
    "سازمان هواشناسی",
]


# ==========================
# Force Join
# ==========================

FORCE_JOIN_ENABLED = True

FORCE_JOIN_CHANNELS = [
    {
        "id": 5156805259,
        "username": "@adminbots_ir",
    }
]
