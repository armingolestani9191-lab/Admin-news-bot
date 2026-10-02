# ==========================
# Support Handler
# Version 1.1.0
# ==========================

from bale import Message

from client import bot

from force_join import (
    is_force_join_enabled,
    is_user_joined
)

from force_join_keyboard import force_join_keyboard

from subscription import get_support_username


async def on_message(message: Message):

    if message.content != "📞 پشتیبانی":
        return

    user = message.from_user

    if is_force_join_enabled():

        if not is_user_joined(user.id):

            await message.reply(
                "⚠️ برای استفاده از ربات ابتدا در کانال زیر عضو شوید.\n\n"
                "پس از عضویت روی دکمه «✅ عضو شدم» بزنید.",
                components=force_join_keyboard()
            )

            return

    support_username = get_support_username()

    await message.reply(
        "📞 پشتیبانی\n\n"
        "اگر سؤال، مشکل یا پیشنهادی دارید، از طریق آیدی زیر با ما در ارتباط باشید.\n\n"
        f"👤 {support_username}"
    )
