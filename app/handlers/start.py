from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.config import ManualPaymentConfig
from app.google_sheets import GoogleSheetsClient, now_in_timezone
from app.keyboards import main_menu_keyboard, manual_payment_review_keyboard, payment_keyboard, support_keyboard
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


def _manual_course_offer_text(manual_payment: ManualPaymentConfig) -> str:
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
        "Реквізити для оплати:\n"
        f"{manual_payment.details}\n\n"
        "Після оплати надішліть сюди скріншот квитанції. "
        "Адміністратор перевірить оплату і відкриє доступ до курсу."
    )


def get_start_router(
    lesson_manager: LessonManager,
    sheets: GoogleSheetsClient,
    payment_manager: PaymentManager | None = None,
    support_username: str = "",
    manual_payment: ManualPaymentConfig | None = None,
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
        elif manual_payment and manual_payment.enabled:
            existing_user = await sheets.find_user(message.from_user.id)
            if not existing_user:
                await message.answer(_manual_course_offer_text(manual_payment))
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

    @router.message(F.photo)
    async def manual_payment_screenshot_handler(message: Message) -> None:
        if not manual_payment or not manual_payment.enabled or not manual_payment.review_chat_id:
            return

        existing_user = await sheets.find_user(message.from_user.id)
        if existing_user:
            await message.answer("Доступ до курсу вже активний.", reply_markup=main_menu_keyboard())
            return

        username = f"@{message.from_user.username}" if message.from_user.username else "немає"
        caption = (
            "Новий скріншот оплати\n\n"
            f"Telegram ID: {message.from_user.id}\n"
            f"Username: {username}\n"
            f"Ім'я: {message.from_user.first_name or ''}"
        )
        await message.bot.send_photo(
            chat_id=manual_payment.review_chat_id,
            photo=message.photo[-1].file_id,
            caption=caption,
            reply_markup=manual_payment_review_keyboard(message.from_user.id),
        )
        await message.answer("Скріншот отримано. Очікуйте перевірки адміністратором.")

    @router.callback_query(F.data.startswith("manual_payment:"))
    async def manual_payment_review_handler(callback: CallbackQuery) -> None:
        if not manual_payment or not manual_payment.enabled:
            await callback.answer("Ручна перевірка вимкнена.", show_alert=True)
            return
        if callback.message.chat.id != manual_payment.review_chat_id:
            await callback.answer()
            return

        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("Некоректна дія.", show_alert=True)
            return

        action = parts[1]
        telegram_id = int(parts[2])
        if action == "reject":
            await callback.bot.send_message(
                telegram_id,
                "Оплату відхилено. Перевірте реквізити або зверніться до підтримки.",
            )
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"Оплату користувача {telegram_id} відхилено.")
            await callback.answer("Відхилено")
            return

        if action != "approve":
            await callback.answer("Некоректна дія.", show_alert=True)
            return

        existing_user = await sheets.find_user(telegram_id)
        if not existing_user:
            await sheets.add_user(
                {
                    "telegram_id": telegram_id,
                    "username": "",
                    "first_name": "",
                    "registered_at": now_in_timezone(sheets.timezone),
                    "current_lesson": 0,
                    "last_lesson_sent_at": "",
                    "next_lesson_at": "",
                    "status": "active",
                }
            )
            existing_user = await sheets.find_user(telegram_id)
        if not existing_user:
            await callback.answer("Не вдалося створити користувача.", show_alert=True)
            return

        await callback.bot.send_message(telegram_id, "Оплату підтверджено. Відкриваю доступ до курсу.")
        await lesson_manager.send_next_lesson(callback.bot, existing_user)
        await sheets.update_statistics()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"Оплату користувача {telegram_id} підтверджено.")
        await callback.answer("Підтверджено")

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
