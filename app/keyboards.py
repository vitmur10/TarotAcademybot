from __future__ import annotations

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
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


def manual_payment_details_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Реквізити для оплати",
            callback_data="manual_payment:details",
            style="primary",
        )
    )
    return builder.as_markup()


def manual_payment_review_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Підтвердити",
            callback_data=f"manual_payment:review:approve:{telegram_id}",
            style="success",
        ),
        InlineKeyboardButton(
            text="❌ Відхилити",
            callback_data=f"manual_payment:review:reject:{telegram_id}",
            style="danger",
        ),
    )
    return builder.as_markup()


def manual_payment_copy_keyboard(copy_items: dict[str, str]) -> InlineKeyboardMarkup | None:
    builder = InlineKeyboardBuilder()
    for label, value in copy_items.items():
        if value:
            builder.row(
                InlineKeyboardButton(
                    text=f"Скопіювати {label}",
                    copy_text=CopyTextButton(text=value),
                )
            )
    markup = builder.as_markup()
    return markup if markup.inline_keyboard else None


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
