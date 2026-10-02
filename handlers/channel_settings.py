from bale import CallbackQuery

from client import bot
from ui import edit_message
from keyboards import (
    channel_settings_menu,
    delete_channel_menu,
    category_menu,
    send_time_menu,
    quiet_hours_menu,
)
from users import (
    delete_channel,
    toggle_channel_image,
    toggle_channel_emoji,
    get_user,
    update_categories,
    update_send_time,
    update_quiet_hours,
)
from states import set_state, get_state, clear_state
from quiet_hours import PRESETS, format_range, parse_custom_range, schedule_of
from subscription import is_free_user, FREE_LOCKED_TIMES
from prices import normalize_categories


CAT_SLUGS = {
    "war": "جنگ",
    "weather": "آب‌وهوا",
    "eco": "طلا و ارز",
    "gold": "طلا و ارز",
    "crypto": "ارز دیجیتال",
    "tech": "فناوری",
    "sport": "ورزش",
    "pol": "سیاسی",
    "all": "همه",
    "جنگ": "جنگ",
    "آب‌وهوا": "آب‌وهوا",
    "اقتصاد": "طلا و ارز",
    "طلا و ارز": "طلا و ارز",
    "ارز دیجیتال": "ارز دیجیتال",
    "فناوری": "فناوری",
    "ورزش": "ورزش",
    "سیاسی": "سیاسی",
    "همه": "همه",
}


def _locks(user_id):
    if is_free_user(user_id):
        # برای اشتراک رایگان فقط «همه دسته‌ها» مجاز است.
        # تمام دسته‌های تکی قفل هستند.
        return [
            "جنگ",
            "آب‌وهوا",
            "طلا و ارز",
            "ارز دیجیتال",
            "فناوری",
            "ورزش",
            "سیاسی",
        ], FREE_LOCKED_TIMES

    return [], set()


def _same_channel(left, right):
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _channel_flags(user, channel_id):
    send_image = True
    show_emoji = True
    categories = ["همه"]
    interval = 10
    schedule = "۲۴ ساعته"

    if not user:
        return send_image, show_emoji, categories, interval, schedule

    for channel in user.get("channels", []):
        if _same_channel(channel.get("id"), channel_id):
            send_image = channel.get("send_image", True)
            show_emoji = channel.get("show_emoji", True)
            categories = normalize_categories(
                channel.get("categories") or ["همه"]
            )
            interval = channel.get("interval", 10)
            start, end = schedule_of(channel)
            schedule = format_range(start, end)
            break

    if "همه" in categories and len(categories) > 1:
        categories = ["همه"]

    return send_image, show_emoji, categories, interval, schedule


def _settings_text(
    channel_id,
    send_image,
    show_emoji,
    categories,
    interval,
    schedule="۲۴ ساعته",
):
    image_state = "روشن" if send_image else "خاموش"
    emoji_state = "روشن" if show_emoji else "خاموش"
    cats = "، ".join(categories) if categories else "همه"

    return (
        f"⚙️ تنظیمات کانال\n\n"
        f"📢 {channel_id}\n"
        f"🖼 عکس: {image_state}\n"
        f"😀 ایموجی: {emoji_state}\n"
        f"⏱ فاصله ارسال: {interval} دقیقه\n"
        f"🏷 دسته‌ها: {cats}\n"
        f"🌙 زمان فعالیت: {schedule}\n\n"
        "از دکمه‌های زیر برای تغییر استفاده کنید."
    )


async def _show_settings(callback, channel_id):
    user = get_user(callback.from_user.id)

    send_image, show_emoji, categories, interval, schedule = _channel_flags(
        user,
        channel_id,
    )

    await edit_message(
        callback,
        _settings_text(
            channel_id,
            send_image,
            show_emoji,
            categories,
            interval,
            schedule,
        ),
        channel_settings_menu(
            channel_id,
            send_image,
            show_emoji,
        ),
    )


def _toggle_categories(selected, category, locked_cats):
    selected = [
        item
        for item in (selected or [])
        if item
    ]

    # دسته قفل‌شده هیچ تغییری ایجاد نمی‌کند.
    if category in locked_cats:
        return selected or ["همه"]

    # انتخاب «همه» تمام انتخاب‌های تکی را کنار می‌گذارد.
    if category == "همه":
        return ["همه"]

    selected = [
        item
        for item in selected
        if item != "همه"
    ]

    if category in selected:
        selected.remove(category)
    else:
        selected.append(category)

    if not selected:
        if locked_cats:
            return [
                item
                for item in ("ورزش", "آب‌وهوا")
                if item not in locked_cats
            ][:1] or ["ورزش"]

        return ["همه"]

    return selected


async def on_callback(callback: CallbackQuery):
    data = callback.data or ""
    user_id = callback.from_user.id

    locked_cats, locked_times = _locks(user_id)

    if data.startswith("csel_") or data.startswith("cat_select_"):
        raw = data.replace("csel_", "", 1).replace(
            "cat_select_",
            "",
            1,
        )

        category = CAT_SLUGS.get(raw, raw)

        state = get_state(user_id)
        payload = dict(state.get("data") or {})
        channel_id = payload.get("channel_id")

        selected = list(
            payload.get("categories") or []
        )

        if not selected:
            user = get_user(user_id) or {}

            _, _, selected, _, _ = _channel_flags(
                user,
                channel_id,
            )

        selected = normalize_categories(selected)

        # کاربر رایگان فقط اجازه «همه» دارد.
        if is_free_user(user_id):
            if category != "همه":
                await edit_message(
                    callback,
                    "🔒 این دسته با اشتراک رایگان قفل است.\n\n"
                    "در اشتراک رایگان فقط «همه دسته‌ها» فعال است.",
                    category_menu(
                        ["همه"],
                        locked_cats,
                    ),
                )
                return

            selected = ["همه"]

        elif category in locked_cats:
            await edit_message(
                callback,
                "این دسته با اشتراک رایگان قفل است.",
                category_menu(
                    selected,
                    locked_cats,
                ),
            )
            return

        else:
            selected = _toggle_categories(
                selected,
                category,
                locked_cats,
            )

        payload["categories"] = selected
        set_state(
            user_id,
            "category_select",
            payload,
        )

        if channel_id:
            update_categories(
                user_id,
                channel_id,
                selected,
            )

        pretty = "، ".join(selected)

        await edit_message(
            callback,
            "🏷 انتخاب دسته‌بندی\n\n"
            f"انتخاب فعلی: {pretty}\n\n"
            "روی هر دسته بزن تا روشن/خاموش شود.\n"
            "بعد ذخیره را بزن.",
            category_menu(
                selected,
                locked_cats,
            ),
        )
        return

    if data.startswith("channel_") and not data.startswith("channel_stats_"):
        await _show_settings(
            callback,
            data.replace("channel_", "", 1),
        )
        return

    if data.startswith("time_"):
        channel_id = data.replace("time_", "", 1)

        await edit_message(
            callback,
            "⏱ فاصله ارسال خبر\n\n"
            "هر چند دقیقه یک خبر جدید فرستاده شود؟",
            send_time_menu(
                channel_id,
                locked_times,
            ),
        )
        return

    if data.startswith("stime_"):
        try:
            parts = data.split("_", 2)
            interval = int(parts[1])
            channel_id = parts[2].strip()

            if interval in locked_times:
                await edit_message(
                    callback,
                    "این زمان با اشتراک رایگان قفل است.",
                    send_time_menu(
                        channel_id,
                        locked_times,
                    ),
                )
                return

            if update_send_time(
                user_id,
                channel_id,
                interval,
            ):
                await _show_settings(
                    callback,
                    channel_id,
                )
            else:
                await edit_message(
                    callback,
                    "زمان ارسال ذخیره نشد.",
                )

        except Exception as error:
            print(
                "خطا در تغییر زمان ارسال:",
                error,
            )

            await edit_message(
                callback,
                "زمان ارسال ذخیره نشد.",
            )

        return

    if data.startswith("img_"):
        channel_id = data.replace(
            "img_",
            "",
            1,
        )

        toggle_channel_image(
            user_id,
            channel_id,
        )

        await _show_settings(
            callback,
            channel_id,
        )
        return

    if data.startswith("emoji_"):
        channel_id = data.replace(
            "emoji_",
            "",
            1,
        )

        toggle_channel_emoji(
            user_id,
            channel_id,
        )

        await _show_settings(
            callback,
            channel_id,
        )
        return

    if data == "csave" or data == "cat_save":
        state = get_state(user_id)
        payload = dict(
            state.get("data") or {}
        )

        channel_id = payload.get("channel_id")

        categories = normalize_categories(
            payload.get("categories") or ["همه"]
        )

        # محدودیت اشتراک رایگان در زمان ذخیره هم
        # دوباره اعمال می‌شود تا هیچ راهی برای ذخیره
        # دسته‌های تکی باقی نماند.
        if is_free_user(user_id):
            categories = ["همه"]

        if not channel_id:
            await edit_message(
                callback,
                "دسته‌بندی ذخیره نشد. دوباره از تنظیمات وارد شو.",
            )
            return

        update_categories(
            user_id,
            channel_id,
            categories,
        )

        clear_state(user_id)

        await _show_settings(
            callback,
            channel_id,
        )
        return

    if data.startswith("cat_") and not data.startswith("cat_select_"):
        channel_id = data.replace(
            "cat_",
            "",
            1,
        )

        user = get_user(user_id)

        _, _, categories, _, _ = _channel_flags(
            user,
            channel_id,
        )

        # اگر کاربر رایگان باشد، تنظیم فعلی کانال
        # حتماً روی «همه» قرار می‌گیرد تا رفتار ارسال
        # دقیقاً مثل حالت «همه» در اشتراک پولی باشد.
        if is_free_user(user_id):
            categories = ["همه"]

            if channel_id:
                update_categories(
                    user_id,
                    channel_id,
                    categories,
                )

        set_state(
            user_id,
            "category_select",
            {
                "channel_id": channel_id,
                "categories": list(categories),
            },
        )

        pretty = "، ".join(categories)

        await edit_message(
            callback,
            "🏷 انتخاب دسته‌بندی\n\n"
            f"انتخاب فعلی: {pretty}\n\n"
            "روی هر دسته بزن تا روشن/خاموش شود.",
            category_menu(
                categories,
                locked_cats,
            ),
        )
        return

    if data.startswith("quiet_"):
        channel_id = data.replace(
            "quiet_",
            "",
            1,
        )

        user = get_user(user_id) or {}

        *_, schedule = _channel_flags(
            user,
            channel_id,
        )

        await edit_message(
            callback,
            "این بخش کمک می‌کنه کانالت طبیعی‌تر به نظر برسه!\n\n"
            f"الان: {schedule}",
            quiet_hours_menu(
                channel_id,
            ),
        )
        return

    if data.startswith("q24_"):
        channel_id = data.replace(
            "q24_",
            "",
            1,
        )

        update_quiet_hours(
            user_id,
            channel_id,
            "",
            "",
        )

        clear_state(user_id)

        await _show_settings(
            callback,
            channel_id,
        )
        return

    if data.startswith("qpre_"):
        try:
            _, index, channel_id = data.split(
                "_",
                2,
            )

            start, end = PRESETS[
                int(index)
            ]

        except Exception:
            await edit_message(
                callback,
                "این بازه ذخیره نشد.",
            )
            return

        update_quiet_hours(
            user_id,
            channel_id,
            start,
            end,
        )

        clear_state(user_id)

        await _show_settings(
            callback,
            channel_id,
        )
        return

    if data.startswith("qcus_"):
        channel_id = data.replace(
            "qcus_",
            "",
            1,
        )

        set_state(
            user_id,
            "quiet_custom",
            {
                "channel_id": channel_id,
            },
        )

        await edit_message(
            callback,
            "ساعت مورد نظر را دقیقاً به این صورت بفرست:\n"
            "۱۳:۰۰ تا ۰۰:۰۰\n\n"
            "بدون متن اضافه باشد.",
        )
        return

    if data.startswith("delete_"):
        channel_id = data.replace(
            "delete_",
            "",
            1,
        )

        await edit_message(
            callback,
            f"حذف کانال {channel_id} انجام شود؟",
            delete_channel_menu(
                channel_id,
            ),
        )
        return

    if data.startswith("yesdel_"):
        channel_id = data.replace(
            "yesdel_",
            "",
            1,
        )

        delete_channel(
            user_id,
            channel_id,
        )

        await edit_message(
            callback,
            "کانال حذف شد.",
        )
        return

    if data.startswith("nodel_"):
        await _show_settings(
            callback,
            data.replace(
                "nodel_",
                "",
                1,
            ),
        )
        return


async def on_message(message):
    if message.from_user is None:
        return

    user_id = message.from_user.id
    state = get_state(user_id)

    if state.get("state") != "quiet_custom":
        return

    text = (message.content or "").strip()

    if text in (
        "🏠 منوی اصلی",
        "🔙 بازگشت",
        "❌ انصراف",
    ):
        return

    parsed, error = parse_custom_range(text)

    channel_id = (
        state.get("data") or {}
    ).get("channel_id")

    if not parsed:
        await message.reply(
            error
            or "بدون متن اضافه باشد.\n"
               "مثال درست: ۱۳:۰۰ تا ۰۰:۰۰"
        )
        return

    if not channel_id:
        clear_state(user_id)

        await message.reply(
            "کانال پیدا نشد. دوباره از تنظیمات وارد شو."
        )
        return

    start, end = parsed

    update_quiet_hours(
        user_id,
        channel_id,
        start,
        end,
    )

    clear_state(user_id)

    await message.reply(
        f"زمان فعالیت این کانال روی "
        f"{format_range(start, end)} تنظیم شد."
            )
