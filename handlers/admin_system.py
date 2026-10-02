import os
import sqlite3
import tempfile

from bale import Message, CallbackQuery
from client import bot

from users import load_users
from admin_store import is_admin
from config import DATABASE_PATH
from sender import send_document_file


def get_all_channels():
    users = load_users()
    channels = []

    for user_id, user in users.items():
        if not isinstance(user, dict):
            continue

        for channel in user.get("channels", []):
            if not isinstance(channel, dict) or not channel.get("id"):
                continue

            channels.append({
                "id": channel["id"],
                "user_id": user_id,
            })

    return channels


def build_channels_page(page=0):
    from handlers.admin_complete import channels_stats_page
    text, keyboard = channels_stats_page(page)
    return text, keyboard


def _stats_users_text():
    from handlers.admin_complete import users_stats_text
    return users_stats_text()


def _create_database_backup():
    if not DATABASE_PATH:
        return None

    if not os.path.isfile(DATABASE_PATH):
        return None

    backup_file = tempfile.NamedTemporaryFile(
        prefix="admin_news_backup_",
        suffix=".db",
        delete=False,
    )
    backup_path = backup_file.name
    backup_file.close()

    source = None
    destination = None

    try:
        source = sqlite3.connect(DATABASE_PATH)
        destination = sqlite3.connect(backup_path)

        source.backup(destination)

        destination.close()
        destination = None

        source.close()
        source = None

        return backup_path

    except Exception:
        try:
            if destination is not None:
                destination.close()
        except Exception:
            pass

        try:
            if source is not None:
                source.close()
        except Exception:
            pass

        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass

        return None


@bot.event
async def on_message(message: Message):
    if message.from_user is None:
        return

    text = (message.content or "").strip()

    admin_texts = {
        "📊 آمار کاربران",
        "📢 آمار کانال‌ها",
        "📰 آمار اخبار",
        "👤 مدیریت کاربران",
        "📺 مدیریت کانال‌ها",
        "👮 ادمین‌ها",
        "📨 ارسال همگانی",
        "⚙️ تنظیمات ربات",
        "🔒 جوین اجباری",
        "🛠 پنل مدیریت",
    }

    if text != "/بکاپ" and text not in admin_texts:
        return

    if not is_admin(message.from_user.id):
        return

    if text == "/بکاپ":
        backup_path = _create_database_backup()

        if not backup_path:
            await message.reply(
                "❌ ساخت بکاپ دیتابیس انجام نشد."
            )
            return

        try:
            result = send_document_file(
                message.from_user.id,
                backup_path,
                caption="🗄 بکاپ کامل دیتابیس ربات",
            )

            if not result.get("ok"):
                await message.reply(
                    "❌ ارسال فایل بکاپ انجام نشد."
                )

        finally:
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            except Exception:
                pass

        return

    from handlers.admin_panel import (
        admin_menu,
        news_today_text,
        join_text,
        join_menu,
        admins_text,
        admins_menu,
        channels_menu,
    )

    from handlers.admin_complete import (
        users_manage_text,
        settings_text,
        channels_stats_page,
    )

    from bale import InlineKeyboardMarkup, InlineKeyboardButton

    if text == "🛠 پنل مدیریت":
        await message.reply(
            "🛠 پنل مدیریت\n\nیک گزینه را انتخاب کن.",
            components=admin_menu(),
        )
        return

    if text == "📊 آمار کاربران":
        await message.reply(
            _stats_users_text(),
            components=_back_admin(),
        )
        return

    if text == "📢 آمار کانال‌ها":
        page_text, keyboard = channels_stats_page(0)
        await message.reply(
            page_text,
            components=keyboard,
        )
        return

    if text == "📰 آمار اخبار":
        await message.reply(
            news_today_text(),
            components=_back_admin(),
        )
        return

    if text == "👤 مدیریت کاربران":
        page_text, keyboard = users_manage_text(0)
        await message.reply(
            page_text,
            components=keyboard,
        )
        return

    if text == "📺 مدیریت کانال‌ها":
        page_text, keyboard = channels_menu(0)
        await message.reply(
            page_text,
            components=keyboard,
        )
        return

    if text == "👮 ادمین‌ها":
        await message.reply(
            admins_text(),
            components=admins_menu(),
        )
        return

    if text == "📨 ارسال همگانی":
        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "👤 همگانی پیوی",
                callback_data="ad_bc_pv",
            ),
            row=1,
        )

        keyboard.add(
            InlineKeyboardButton(
                "📢 همگانی کانال‌ها",
                callback_data="ad_bc_ch",
            ),
            row=2,
        )

        keyboard.add(
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="ad_home",
            ),
            row=3,
        )

        await message.reply(
            "📨 همگانی\n\nکجا ارسال شود؟",
            components=keyboard,
        )
        return

    if text == "⚙️ تنظیمات ربات":
        await message.reply(
            settings_text(),
            components=_back_admin(),
        )
        return

    if text == "🔒 جوین اجباری":
        await message.reply(
            join_text(),
            components=join_menu(),
        )
        return


def _back_admin():
    from handlers.admin_panel import back_admin
    return back_admin()


@bot.event
async def on_callback_query(query: CallbackQuery):
    data = query.data or ""

    if not data.startswith("channel_stats_"):
        return

    if query.from_user and not is_admin(query.from_user.id):
        return

    page = (
        int(data.split("_")[-1])
        if data.split("_")[-1].isdigit()
        else 0
    )

    text, keyboard = build_channels_page(page)

    try:
        await query.message.edit(
            text,
            components=keyboard,
        )
    except Exception:
        await query.message.reply(
            text,
            components=keyboard,
        )
