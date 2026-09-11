from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.google_sheets import GoogleSheetsClient
from app.keyboards import main_menu_keyboard, payment_keyboard, support_keyboard
from app.lessons import LessonManager
from app.payments import PaymentManager

LOGGER = logging.getLogger(__name__)


def get_start_router(
    lesson_manager: LessonManager,
    sheets: GoogleSheetsClient,
    payment_manager: PaymentManager | None = None,
    support_username: str = "",
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        if payment_manager:
            existing_user = await sheets.find_user(message.from_user.id)
            if not existing_user:
                payment = await payment_manager.create_payment_for_user(message.from_user)
                await message.answer(
                    "Щоб отримати доступ до курсу, оплатіть участь. "
                    "Після підтвердження оплати бот автоматично надішле перший урок.",
                    reply_markup=payment_keyboard(payment.checkout.payment_page_url),
                )
                return

        result = await lesson_manager.register_and_send_first_lesson(message.bot, message.from_user)
        if result.delivered:
            return

        if result.completed_course:
            text = "Ви вже завершили курс."
        else:
            text = "Ви вже зареєстровані. Курс продовжується за вашим поточним графіком."
        await message.answer(text, reply_markup=main_menu_keyboard())

    @router.message(Command("help"))
    @router.message(F.text == "ℹ️ Допомога")
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Що потрібно зробити:\n\n"
            "1. Натисніть /start, щоб почати курс або відкрити меню.\n"
            "2. Якщо увімкнена оплата, натисніть кнопку «Оплатити курс». "
            "Після підтвердження платежу бот автоматично відкриє перший урок.\n"
            "3. У розділі «📚 Мій курс» можна подивитися поточний стан курсу.\n"
            "4. У розділі «📊 Мій прогрес» показано, скільки уроків уже пройдено.\n\n"
            "Якщо виникли питання з оплатою, доступом або роботою кнопок, зверніться до підтримки.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(F.text == "💬 Підтримка")
    async def support_handler(message: Message) -> None:
        if not support_username:
            await message.answer(
                "Контакт підтримки ще не налаштовано.",
                reply_markup=main_menu_keyboard(),
            )
            return

        await message.answer(
            "Напишіть підтримці в Telegram.",
            reply_markup=support_keyboard(support_username),
        )

    return router
