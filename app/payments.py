from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.types import User

from app.google_sheets import GoogleSheetsClient, now_in_timezone
from app.lessons import LessonManager
from app.liqpay import LiqPayCheckout, LiqPayClient

LOGGER = logging.getLogger(__name__)

SUCCESS_PAYMENT_STATUSES = {"success", "sandbox"}


@dataclass(slots=True)
class PaymentStartResult:
    checkout: LiqPayCheckout


class PaymentManager:
    def __init__(self, sheets: GoogleSheetsClient, liqpay: LiqPayClient, lesson_manager: LessonManager) -> None:
        self.sheets = sheets
        self.liqpay = liqpay
        self.lesson_manager = lesson_manager

    async def create_payment_for_user(self, telegram_user: User) -> PaymentStartResult:
        order_id = self._create_order_id(telegram_user.id)
        checkout = self.liqpay.create_checkout(order_id=order_id, telegram_id=telegram_user.id)
        await self.sheets.add_payment(
            {
                "order_id": order_id,
                "telegram_id": telegram_user.id,
                "username": telegram_user.username or "",
                "first_name": telegram_user.first_name or "",
                "amount": self.liqpay.config.amount,
                "currency": self.liqpay.config.currency,
                "status": "created",
                "created_at": now_in_timezone(self.sheets.timezone),
                "paid_at": "",
                "liqpay_payment_id": "",
                "raw_status": "",
            }
        )
        return PaymentStartResult(checkout=checkout)

    async def get_checkout(self, order_id: str) -> LiqPayCheckout | None:
        payment = await self.sheets.find_payment(order_id)
        if not payment:
            return None
        return self.liqpay.create_checkout(order_id=order_id, telegram_id=payment["telegram_id"])

    async def process_callback(self, bot: Bot, data: str, signature: str) -> bool:
        if not self.liqpay.verify_signature(data, signature):
            LOGGER.warning("Invalid LiqPay callback signature")
            return False

        payload = self.liqpay.decode_data(data)
        order_id = str(payload.get("order_id", "")).strip()
        status = str(payload.get("status", "")).strip()
        payment_id = str(payload.get("payment_id", "")).strip()

        if not order_id:
            LOGGER.warning("LiqPay callback without order_id")
            return False

        payment = await self.sheets.find_payment(order_id)
        if not payment:
            LOGGER.warning("LiqPay callback for unknown order_id: %s", order_id)
            return False

        updates: dict[str, Any] = {
            "status": "paid" if status in SUCCESS_PAYMENT_STATUSES else status,
            "raw_status": status,
            "liqpay_payment_id": payment_id,
        }
        if status in SUCCESS_PAYMENT_STATUSES:
            updates["paid_at"] = now_in_timezone(self.sheets.timezone)
        await self.sheets.update_payment(order_id, updates)

        if status not in SUCCESS_PAYMENT_STATUSES:
            return True

        telegram_id = payment["telegram_id"]
        existing_user = await self.sheets.find_user(telegram_id)
        if existing_user:
            return True

        await self.sheets.add_user(
            {
                "telegram_id": telegram_id,
                "username": payment["username"],
                "first_name": payment["first_name"],
                "registered_at": now_in_timezone(self.sheets.timezone),
                "current_lesson": 0,
                "last_lesson_sent_at": "",
                "next_lesson_at": "",
                "status": "active",
            }
        )
        user = await self.sheets.find_user(telegram_id)
        if not user:
            raise RuntimeError("Paid user was not created in Users sheet")

        await bot.send_message(telegram_id, "Оплату отримано. Відкриваю доступ до курсу.")
        await self.lesson_manager.send_next_lesson(bot, user)
        await self.sheets.update_statistics()
        return True

    def _create_order_id(self, telegram_id: int) -> str:
        timestamp = now_in_timezone(self.sheets.timezone).strftime("%Y%m%d%H%M%S")
        suffix = secrets.token_hex(4)
        return f"tarot_{telegram_id}_{timestamp}_{suffix}"
