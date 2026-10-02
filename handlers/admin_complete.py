from datetime import datetime

from bale import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from client import bot
from ui import edit_message
from users import load_users, get_user, search_users
from admin_store import is_admin, load_join_channels, OWNER_ID
from subscription import (
    subscription_info,
    get_card_number,
    set_card_number,
    activate_subscription,
    clear_subscription,
    get_all_plans,
    set_plan_price,
    get_support_username,
    set_support_username,
)
from handlers import admin_panel
from handlers.admin_panel import back_admin, all_registered_channels
from handlers.home import home_components
from force_join import is_force_join_enabled
from states import set_state, clear_state, get_state
from bans import is_banned, ban_user, unban_user
from sender import send_message


def admin_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📨 همگانی", callback_data="ad_bc"), row=1)
    keyboard.add(InlineKeyboardButton("📊 آمار کاربران", callback_data="ad_ustats"), row=2)
    keyboard.add(InlineKeyboardButton("📺 آمار کانال‌ها", callback_data="ad_cstats"), row=2)
    keyboard.add(InlineKeyboardButton("📰 آمار اخبار", callback_data="ad_news"), row=3)
    keyboard.add(InlineKeyboardButton("👤 مدیریت کاربران", callback_data="ad_umgmt"), row=4)
    keyboard.add(InlineKeyboardButton("📺 مدیریت کانال‌ها", callback_data="ad_chs"), row=5)
    keyboard.add(InlineKeyboardButton("👮 ادمین‌ها", callback_data="ad_admins"), row=6)
    keyboard.add(InlineKeyboardButton("🔒 جوین اجباری", callback_data="ad_join"), row=7)
    keyboard.add(InlineKeyboardButton("⚙️ تنظیمات ربات", callback_data="ad_set"), row=8)
    keyboard.add(InlineKeyboardButton("💳 تغییر شماره کارت", callback_data="ad_card"), row=9)
    keyboard.add(InlineKeyboardButton("🔙 منوی اصلی", callback_data="m_home"), row=10)
    return keyboard


admin_panel.admin_menu = admin_menu


def users_stats_text():
    users = load_users(force=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_users = 0
    active_sub = 0

    for user in users.values():
        if not isinstance(user, dict):
            continue

        if str(user.get("join_date") or "").startswith(today):
            today_users += 1

    for user_id in users:
        if subscription_info(user_id)["active"]:
            active_sub += 1

    return (
        "📊 آمار کاربران\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 کل کاربران: {len(users)}\n"
        f"🆕 جدید امروز: {today_users}\n"
        f"⭐ اشتراک فعال: {active_sub}"
    )


def channels_stats_page(page=0):
    items = all_registered_channels()
    active = sum(
        1
        for item in items
        if item.get("status") == "active"
    )

    per_page = 30

    total_pages = max(
        1,
        (len(items) + per_page - 1) // per_page,
    )

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * per_page

    lines = [
        "📺 آمار کانال‌ها",
        "━━━━━━━━━━━━━━",
        f"📢 کل کانال‌ها: {len(items)}",
        f"🟢 فعال: {active}",
        f"🔴 متوقف: {len(items) - active}",
        f"📄 صفحه {page + 1}/{total_pages}",
        "",
    ]

    chunk = items[
        start:start + per_page
    ]

    if not chunk:
        lines.append(
            "هنوز کانالی ثبت نشده."
        )
    else:
        for index, item in enumerate(
            chunk,
            start=start + 1,
        ):
            owner = (
                item.get("owner_username")
                or item.get("owner_id")
                or item.get("owner_name")
            )

            if (
                owner
                and not str(owner).startswith("@")
                and not str(owner).isdigit()
            ):
                owner = "@" + str(owner)

            lines.append(
                f"{index}. {item.get('id')}"
            )
            lines.append(
                f"└ 👤 افزوده شده توسط: {owner}"
            )
            lines.append("")

    keyboard = InlineKeyboardMarkup()

    nav = []

    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️",
                callback_data=f"ad_cstats_{page - 1}",
            )
        )

    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                "➡️",
                callback_data=f"ad_cstats_{page + 1}",
            )
        )

    if nav:
        keyboard.add(
            *nav,
            row=1,
        )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="ad_home",
        ),
        row=2,
    )

    return "\n".join(lines), keyboard


def channels_stats_text(page=0):
    text, _keyboard = channels_stats_page(page)
    return text


# ==========================================================
# User Management
# ==========================================================

def _user_rows():
    rows = []
    users = load_users(force=True)

    for user_id, user in users.items():
        if not isinstance(user, dict):
            continue

        info = subscription_info(user_id)

        # فقط کاربران دارای اشتراک فعال در دکمه‌ها
        if not info["active"]:
            continue

        username = user.get("username")

        mention = (
            ("@" + str(username).lstrip("@"))
            if username
            else str(user_id)
        )

        rows.append(
            (
                str(user_id),
                mention,
                info,
            )
        )

    rows.sort(
        key=lambda item: item[1].lower()
    )

    return rows


def find_user_query(text):
    return search_users(text)


def users_manage_text(page=0):
    users = load_users(force=True)
    rows = _user_rows()

    active_count = sum(
        1
        for _uid, _mention, info in rows
        if info["active"]
    )

    per_page = 8

    total_pages = max(
        1,
        (len(rows) + per_page - 1) // per_page,
    )

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * per_page
    end = start + per_page

    chunk = rows[start:end]

    lines = [
        "👤 مدیریت کاربران",
        "━━━━━━━━━━━━━━",
        f"👥 تعداد کل کاربران: {len(users)}",
        f"⭐ اشتراک فعال (رایگان و پولی): {active_count}",
        f"📄 صفحه {page + 1}/{total_pages}",
        "",
        "روی اسم کاربر بزن تا اطلاعاتش باز شود.",
        "یا با دکمه جستجو آیدی / یوزرنیم بفرست.",
    ]

    keyboard = InlineKeyboardMarkup()

    row_i = 1

    keyboard.add(
        InlineKeyboardButton(
            "🔎 جستجو با آیدی یا یوزرنیم",
            callback_data="ad_ufind",
        ),
        row=row_i,
    )

    row_i += 1

    if not chunk:
        keyboard.add(
            InlineKeyboardButton(
                "هنوز کاربری ثبت نشده",
                callback_data="ad_ignore",
            ),
            row=row_i,
        )

        row_i += 1

    else:
        for user_id, mention, info in chunk:
            label = (
                f"⭐ {mention} | "
                f"{info['remaining']}روز"
            )

            keyboard.add(
                InlineKeyboardButton(
                    label,
                    callback_data=f"ad_uv_{user_id}",
                ),
                row=row_i,
            )

            row_i += 1

    # ======================================================
    # Pagination
    # ======================================================

    nav = []

    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️",
                callback_data=f"ad_umgmt_{page - 1}",
            )
        )

    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                "➡️",
                callback_data=f"ad_umgmt_{page + 1}",
            )
        )

    if nav:
        keyboard.add(
            *nav,
            row=row_i,
        )

        row_i += 1

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="ad_home",
        ),
        row=row_i,
    )

    return "\n".join(lines), keyboard


def user_detail_view(target_id):
    user = get_user(
        target_id,
        force=True,
    )

    if not user:
        keyboard = InlineKeyboardMarkup()

        keyboard.add(
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="ad_umgmt",
            ),
            row=1,
        )

        return "کاربر پیدا نشد.", keyboard

    info = subscription_info(target_id)

    username = user.get("username")

    mention = (
        "@" + str(username).lstrip("@")
        if username
        else "ندارد"
    )

    channels = user.get("channels") or []

    if channels:
        channel_lines = "\n".join(
            f"{index}. {item.get('id')}"
            for index, item in enumerate(
                channels,
                start=1,
            )
        )
    else:
        channel_lines = "ندارد"

    banned = (
        "بله"
        if is_banned(target_id)
        else "خیر"
    )

    text = (
        "👤 اطلاعات کاربر\n"
        "━━━━━━━━━━━━━━\n"
        f"یوزرنیمش: {mention}\n"
        f"ایدی عددیش: {target_id}\n"
        f"کانالی که اد داده:\n{channel_lines}\n"
        f"اشتراکش چند وقت مونده: {info['remaining']} روز\n"
        f"نوع اشتراک: {info['label']}\n"
        f"بن: {banned}"
    )

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "🚫 بن کاربر",
            callback_data=f"ad_ban_{target_id}",
        ),
        row=1,
    )

    keyboard.add(
        InlineKeyboardButton(
            "✅ آنبن کاربر",
            callback_data=f"ad_unban_{target_id}",
        ),
        row=1,
    )

    keyboard.add(
        InlineKeyboardButton(
            "✉️ پیام به کاربر",
            callback_data=f"ad_umsg_{target_id}",
        ),
        row=2,
    )

    keyboard.add(
        InlineKeyboardButton(
            "🗑 حذف اشتراک",
            callback_data=f"ad_usubdel_{target_id}",
        ),
        row=3,
    )

    keyboard.add(
        InlineKeyboardButton(
            "⭐ دادن اشتراک ۱۰ روز",
            callback_data=f"ad_usub10_{target_id}",
        ),
        row=3,
    )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="ad_umgmt",
        ),
        row=4,
    )

    return text, keyboard


# ==========================
# Bot Settings
# ==========================

def settings_text():
    join = load_join_channels()

    status = (
        "روشن"
        if is_force_join_enabled() and join
        else "خاموش"
    )

    plans = get_all_plans()

    plan_lines = []

    for plan_id, plan in plans.items():
        price = f"{int(plan['price']):,}".replace(",", "٬")

        plan_lines.append(
            f"💎 {plan['title']}: {price} تومان"
        )

    return (
        "⚙️ تنظیمات ربات\n"
        "━━━━━━━━━━━━━━\n"
        f"💳 کارت: {get_card_number()}\n"
        f"🆘 پشتیبانی: {get_support_username()}\n"
        f"🔒 جوین اجباری: {status}\n"
        f"📢 کانال‌های جوین: {len(join)}/3\n"
        "\n"
        "💎 قیمت اشتراک‌ها:\n"
        + "\n".join(plan_lines)
    )


def settings_menu():
    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            "💳 تغییر شماره کارت",
            callback_data="ad_card",
        ),
        row=1,
    )

    keyboard.add(
        InlineKeyboardButton(
            "💎 تنظیم قیمت اشتراک‌ها",
            callback_data="ad_prices",
        ),
        row=2,
    )

    keyboard.add(
        InlineKeyboardButton(
            "🆘 تغییر آیدی پشتیبانی",
            callback_data="ad_support",
        ),
        row=3,
    )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="ad_home",
        ),
        row=4,
    )

    return keyboard


def prices_menu():
    keyboard = InlineKeyboardMarkup()

    plans = get_all_plans()

    row = 1

    for plan_id, plan in plans.items():
        price = f"{int(plan['price']):,}".replace(",", "٬")

        keyboard.add(
            InlineKeyboardButton(
                f"💎 {plan['title']} | {price} تومان",
                callback_data=f"ad_price_{plan_id}",
            ),
            row=row,
        )

        row += 1

    keyboard.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="ad_set",
        ),
        row=row,
    )

    return keyboard


# ==========================
# Callbacks
# ==========================

@bot.event
async def on_callback(callback: CallbackQuery):
    data = str(callback.data or "")
    user_id = callback.from_user.id

    if not (
        data.startswith("ad_")
        or data.startswith("channel_stats_")
    ):
        return

    if not is_admin(user_id):
        await edit_message(
            callback,
            "🚫 این بخش فقط برای ادمین است.",
            home_components(user_id),
        )
        return

    if data == "ad_ustats":
        await edit_message(
            callback,
            users_stats_text(),
            back_admin(),
        )
        return

    if (
        data == "ad_cstats"
        or data.startswith("ad_cstats_")
        or data.startswith("channel_stats_")
    ):
        page = 0

        if data.startswith("ad_cstats_"):
            page_text = data.split(
                "ad_cstats_",
                1,
            )[1]

            if page_text.isdigit():
                page = int(page_text)

        elif data.startswith("channel_stats_"):
            page_text = data.split(
                "channel_stats_",
                1,
            )[1]

            if page_text.isdigit():
                page = int(page_text)

        text, keyboard = channels_stats_page(page)

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    # ======================================================
    # Channel Management
    # ======================================================

    if data == "ad_chs" or data.startswith("ad_chs_"):
        page = 0

        if data.startswith("ad_chs_"):
            page_text = data.split(
                "ad_chs_",
                1,
            )[1]

            if not page_text.isdigit():
                return

            page = int(page_text)

        text, keyboard = admin_panel.channels_menu(page)

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    if data.startswith("ad_ch_"):
        index_text = data.split(
            "ad_ch_",
            1,
        )[1]

        if not index_text.isdigit():
            return

        text, keyboard = admin_panel.channel_detail(
            int(index_text)
        )

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    if data.startswith("ad_pause_") or data.startswith("ad_run_"):
        pause = data.startswith("ad_pause_")
        index_text = data.split("_")[-1]

        if not index_text.isdigit():
            return

        index = int(index_text)
        items = admin_panel.all_registered_channels()

        if index < 0 or index >= len(items):
            await edit_message(
                callback,
                "کانال پیدا نشد.",
                back_admin(),
            )
            return

        item = items[index]

        set_channel_status(
            item["owner_id"],
            item["id"],
            "paused" if pause else "active",
        )

        text, keyboard = admin_panel.channel_detail(index)

        prefix = (
            "⏸️ متوقف شد"
            if pause
            else "▶️ ران شد"
        )

        await edit_message(
            callback,
            prefix + "\n\n" + text,
            keyboard,
        )

        return

    # ======================================================
    # User Management Pagination
    # ======================================================

    if data == "ad_umgmt":
        text, keyboard = users_manage_text(0)

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    if data.startswith("ad_umgmt_"):
        page_text = data.split(
            "ad_umgmt_",
            1,
        )[1]

        # فقط شماره صفحه معتبر قبول شود
        if not page_text.isdigit():
            return

        page = int(page_text)

        text, keyboard = users_manage_text(page)

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    if data == "ad_ufind":
        set_state(
            user_id,
            "admin_user_find",
            {},
        )

        await edit_message(
            callback,
            "🔎 آیدی عددی یا یوزرنیم کاربر را بفرست.\n"
            "مثال: 123456789 یا @username",
            back_admin(),
        )

        return

    if data.startswith("ad_uv_"):
        target = data.replace(
            "ad_uv_",
            "",
            1,
        )

        text, keyboard = user_detail_view(
            target
        )

        await edit_message(
            callback,
            text,
            keyboard,
        )

        return

    if data.startswith("ad_ban_"):
        target = data.replace(
            "ad_ban_",
            "",
            1,
        )

        if (
            str(target) == str(OWNER_ID)
            or is_admin(target)
        ):
            await edit_message(
                callback,
                "⚠️ ادمین را نمی‌شود بن کرد.",
                user_detail_view(target)[1],
            )
            return

        ban_user(target)

        send_message(
            target,
            "حساب شما توسط پشتیبانی بن شد.",
        )

        text, keyboard = user_detail_view(
            target
        )

        await edit_message(
            callback,
            "✅ کاربر بن شد.\n\n" + text,
            keyboard,
        )

        return

    if data.startswith("ad_unban_"):
        target = data.replace(
            "ad_unban_",
            "",
            1,
        )

        unban_user(target)

        send_message(
            target,
            "حساب شما توسط پشتیبانی آنبن شد و از الان میتونید با رعایت قوانین از ربات استفاده کنید",
        )

        text, keyboard = user_detail_view(
            target
        )

        await edit_message(
            callback,
            "✅ کاربر آنبن شد.\n\n" + text,
            keyboard,
        )

        return

    if data.startswith("ad_umsg_"):
        target = data.replace(
            "ad_umsg_",
            "",
            1,
        )

        set_state(
            user_id,
            "admin_user_msg",
            {
                "target_id": target,
            },
        )

        await edit_message(
            callback,
            "✉️ متن پیام را بفرست. فقط برای همین کاربر می‌رود.",
            back_admin(),
        )

        return

    if data.startswith("ad_usubdel_"):
        target = data.replace(
            "ad_usubdel_",
            "",
            1,
        )

        clear_subscription(target)

        text, keyboard = user_detail_view(
            target
        )

        await edit_message(
            callback,
            "✅ اشتراک کاربر حذف شد.\n\n" + text,
            keyboard,
        )

        return

    if data.startswith("ad_usub10_"):
        target = data.replace(
            "ad_usub10_",
            "",
            1,
        )

        activate_subscription(
            target,
            "paid",
            10,
        )

        text, keyboard = user_detail_view(
            target
        )

        await edit_message(
            callback,
            "✅ اشتراک ۱۰ روزه برای کاربر فعال شد.\n\n" + text,
            keyboard,
        )

        return

    # ==========================
    # Card
    # ==========================

    if data == "ad_card":
        set_state(
            user_id,
            "admin_card",
            {},
        )

        await edit_message(
            callback,
            "💳 شماره کارت جدید را وارد کن.\n"
            "فقط عدد کارت را بفرست.",
            back_admin(),
        )

        return

    # ==========================
    # Settings
    # ==========================

    if data == "ad_set":
        await edit_message(
            callback,
            settings_text(),
            settings_menu(),
        )

        return

    # ==========================
    # Subscription Prices
    # ==========================

    if data == "ad_prices":
        await edit_message(
            callback,
            "💎 تنظیم قیمت اشتراک‌ها\n"
            "━━━━━━━━━━━━━━\n"
            "روی اشتراکی که می‌خواهی قیمتش را تغییر بده بزن:",
            prices_menu(),
        )

        return

    if data.startswith("ad_price_"):
        plan_id = data.replace(
            "ad_price_",
            "",
            1,
        )

        plans = get_all_plans()
        plan = plans.get(plan_id)

        if not plan:
            await edit_message(
                callback,
                "⚠️ اشتراک پیدا نشد.",
                prices_menu(),
            )
            return

        set_state(
            user_id,
            "admin_plan_price",
            {
                "plan_id": plan_id,
            },
        )

        current_price = f"{int(plan['price']):,}".replace(
            ",",
            "٬",
        )

        await edit_message(
            callback,
            f"💎 تغییر قیمت اشتراک {plan['title']}\n"
            "━━━━━━━━━━━━━━\n"
            f"💰 قیمت فعلی: {current_price} تومان\n\n"
            "قیمت جدید را فقط به صورت عدد بفرست.\n"
            "مثال: 45000",
            back_admin(),
        )

        return

    # ==========================
    # Support Username
    # ==========================

    if data == "ad_support":
        set_state(
            user_id,
            "admin_support_username",
            {},
        )

        await edit_message(
            callback,
            "🆘 تغییر آیدی پشتیبانی\n"
            "━━━━━━━━━━━━━━\n"
            f"آیدی فعلی: {get_support_username()}\n\n"
            "آیدی جدید را بفرست.\n"
            "مثال: @support\n"
            "یا بدون @ مثل: support",
            back_admin(),
        )

        return


# ==========================
# Messages
# ==========================

@bot.event
async def on_message(message: Message):
    if message.from_user is None:
        return

    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    state = get_state(user_id)

    name = state.get("state")

    text = (
        message.content or ""
    ).strip()

    # ==========================
    # Card
    # ==========================

    if name == "admin_card":
        number = set_card_number(text)

        clear_state(user_id)

        if not number:
            await message.reply(
                "⚠️ شماره کارت درست نیست. فقط عدد کارت را بفرست.",
                components=settings_menu(),
            )
            return

        await message.reply(
            f"✅ شماره کارت عوض شد.\n\n"
            f"از این بعد در خرید اشتراک این کارت می‌آید:\n"
            f"`{number}`",
            components=admin_menu(),
        )

        return

    # ==========================
    # Subscription Price
    # ==========================

    if name == "admin_plan_price":
        data = state.get("data") or {}

        plan_id = str(
            data.get("plan_id") or ""
        )

        plans = get_all_plans()
        plan = plans.get(plan_id)

        if not plan:
            clear_state(user_id)

            await message.reply(
                "⚠️ اشتراک پیدا نشد.",
                components=settings_menu(),
            )

            return

        raw_price = (
            text
            .replace(",", "")
            .replace("٬", "")
            .replace(" ", "")
        )

        if not raw_price.isdigit():
            await message.reply(
                "⚠️ قیمت نامعتبر است.\n"
                "فقط عدد بفرست.\n\n"
                "مثال: 45000",
                components=back_admin(),
            )
            return

        price = int(raw_price)

        if price < 0:
            await message.reply(
                "⚠️ قیمت نمی‌تواند منفی باشد.",
                components=back_admin(),
            )
            return

        if not set_plan_price(
            plan_id,
            price,
        ):
            await message.reply(
                "❌ ذخیره قیمت انجام نشد.",
                components=settings_menu(),
            )
            clear_state(user_id)
            return

        clear_state(user_id)

        formatted_price = f"{price:,}".replace(
            ",",
            "٬",
        )

        await message.reply(
            f"✅ قیمت اشتراک {plan['title']} تغییر کرد.\n\n"
            f"💰 قیمت جدید: {formatted_price} تومان\n\n"
            "این قیمت در SQLite ذخیره شد و بعد از ری‌استارت ربات هم باقی می‌ماند.",
            components=settings_menu(),
        )

        return

    # ==========================
    # Support Username
    # ==========================

    if name == "admin_support_username":
        username = text

        if not username:
            await message.reply(
                "⚠️ آیدی پشتیبانی نمی‌تواند خالی باشد.\n"
                "مثال: @support",
                components=back_admin(),
            )
            return

        if not set_support_username(
            username
        ):
            await message.reply(
                "❌ ذخیره آیدی پشتیبانی انجام نشد.",
                components=settings_menu(),
            )
            clear_state(user_id)
            return

        clear_state(user_id)

        await message.reply(
            f"✅ آیدی پشتیبانی تغییر کرد.\n\n"
            f"🆘 آیدی جدید: {get_support_username()}\n\n"
            "این مقدار در SQLite ذخیره شد و بعد از ری‌استارت ربات هم باقی می‌ماند.",
            components=settings_menu(),
        )

        return

    # ==========================
    # User Find
    # ==========================

    if name == "admin_user_find":
        clear_state(user_id)

        target = find_user_query(text)

        if not target:
            text_page, keyboard = users_manage_text(0)

            await message.reply(
                "⚠️ کاربر پیدا نشد.\n"
                "آیدی یا یوزرنیم را دوباره بفرست.\n\n"
                + text_page,
                components=keyboard,
            )

            return

        detail, keyboard = user_detail_view(
            target
        )

        await message.reply(
            detail,
            components=keyboard,
        )

        return

    # ==========================
    # User Message
    # ==========================

    if name == "admin_user_msg":
        target = (
            state.get("data") or {}
        ).get("target_id")

        clear_state(user_id)

        if not target or not text:
            await message.reply(
                "⚠️ پیام ارسال نشد.",
                components=back_admin(),
            )
            return

        send_message(
            target,
            text,
        )

        await message.reply(
            "✅ پیام برای کاربر ارسال شد.",
            components=user_detail_view(target)[1],
        )

        return
