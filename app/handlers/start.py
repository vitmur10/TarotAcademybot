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


COMPANY_INFO_TEXT = (
    "🏢 О компанії\n\n"
    "Tarot Academy\n\n"
    "Онлайн-платформа для навчання роботі з картами Таро.\n\n"
    "Продавець: ФОП Гавриш Борис Григорійович\n\n"
    "РНОКПП: 3824704579\n\n"
    "Вид діяльності: продажа онлайн-курса по навчанню роботі з картами Таро.\n\n"
    "Контактний email:\n"
    "smirnovacarolina170@gmail.com"
)


def _course_offer_text(payment_manager: PaymentManager) -> str:
    amount = int(payment_manager.liqpay.config.amount)
    currency = payment_manager.liqpay.config.currency
    return (
        "🔮 База Таро за 9 днів\n\n"
        "Опис:\n\n"
        "Онлайн-курс для навчання основам роботи з картами Таро.\n\n"
        "В курс входить:\n\n"
        "• 9 навчальних уроків\n"
        "• навчання роботі з картами Таро\n"
        "• розуміння значень і трактовок карт\n"
        "• правильний підхід до роботи з Таро\n"
        "• домашні завдання для закріплення матеріала\n\n"
        f"💰 Вартість: {amount} {currency}\n\n"
        "🕐 Доступ к курсу: 1 год"
    )


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
                    _course_offer_text(payment_manager),
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
            "Інформація про продавця доступна в розділі «🏢 Про компанію».\n"
            "Якщо виникли питання з оплатою, доступом або роботою кнопок, зверніться до підтримки.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(F.text == "🏢 Про компанію")
    async def company_info_handler(message: Message) -> None:
        await message.answer(COMPANY_INFO_TEXT, reply_markup=main_menu_keyboard())

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
