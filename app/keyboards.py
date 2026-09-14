from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Мій курс")],
            [KeyboardButton(text="📊 Мій прогрес")],
            [KeyboardButton(text="ℹ️ Допомога")],
            [KeyboardButton(text="🏢 Про компанію")],
            [KeyboardButton(text="💬 Підтримка")],
        ],
        resize_keyboard=True,
    )


def payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплатити курс", url=payment_url))
    return builder.as_markup()


def manual_payment_review_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Підтвердити",
            callback_data=f"manual_payment:approve:{telegram_id}",
            style="success",
        ),
        InlineKeyboardButton(
            text="❌ Відхилити",
            callback_data=f"manual_payment:reject:{telegram_id}",
            style="danger",
        ),
    )
    return builder.as_markup()


def support_keyboard(support_username: str) -> InlineKeyboardMarkup | None:
    if not support_username:
        return None

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Зв'язатися з підтримкою",
            url=f"https://t.me/{support_username}",
        )
    )
    return builder.as_markup()


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Підтвердити", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="Скасувати", callback_data="broadcast:cancel"),
    )
    return builder.as_markup()
