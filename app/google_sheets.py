from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

LESSONS_SHEET = "Lessons"
USERS_SHEET = "Users"
STATISTICS_SHEET = "Statistics"
PAYMENTS_SHEET = "Payments"

LESSONS_HEADERS = [
    "lesson_number",
    "title",
    "text",
    "video_file_id",
    "document_file_id",
    "delay_hours",
    "active",
]
USERS_HEADERS = [
    "telegram_id",
    "username",
    "first_name",
    "registered_at",
    "current_lesson",
    "last_lesson_sent_at",
    "next_lesson_at",
    "status",
]
STATISTICS_HEADERS = ["metric", "value"]
PAYMENTS_HEADERS = [
    "order_id",
    "telegram_id",
    "username",
    "first_name",
    "amount",
    "currency",
    "status",
    "created_at",
    "paid_at",
    "liqpay_payment_id",
    "raw_status",
]

LOGGER = logging.getLogger(__name__)


def now_in_timezone(timezone: ZoneInfo) -> datetime:
    return datetime.now(timezone)


def datetime_to_str(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def str_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


class GoogleSheetsClient:
    def __init__(self, spreadsheet_id: str, credentials_file: str, timezone: ZoneInfo) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file
        self.timezone = timezone
        self._client: gspread.Client | None = None
        self._spreadsheet: gspread.Spreadsheet | None = None
        self._lessons_cache: list[dict[str, Any]] = []
        self._lessons_cache_at = 0.0
        self._lessons_cache_ttl = 120

    async def get_lessons(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        if not force_refresh and self._lessons_cache and time.time() - self._lessons_cache_at < self._lessons_cache_ttl:
            return list(self._lessons_cache)

        lessons = await asyncio.to_thread(self._get_lessons_sync)
        self._lessons_cache = lessons
        self._lessons_cache_at = time.time()
        return list(lessons)

    async def find_user(self, telegram_id: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._find_user_sync, telegram_id)

    async def add_user(self, user_data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._add_user_sync, user_data)

    async def update_user(self, telegram_id: int, updates: dict[str, Any]) -> None:
        await asyncio.to_thread(self._update_user_sync, telegram_id, updates)

    async def get_users(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._get_users_sync)

    async def get_active_users(self) -> list[dict[str, Any]]:
        users = await self.get_users()
        return [user for user in users if user["status"] == "active"]

    async def update_statistics(self) -> None:
        await asyncio.to_thread(self._update_statistics_sync)

    async def add_payment(self, payment_data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._add_payment_sync, payment_data)

    async def find_payment(self, order_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._find_payment_sync, order_id)

    async def update_payment(self, order_id: str, updates: dict[str, Any]) -> None:
        await asyncio.to_thread(self._update_payment_sync, order_id, updates)

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
            self._client = gspread.authorize(credentials)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet is None:
            self._spreadsheet = self._get_client().open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def _worksheet(self, title: str) -> gspread.Worksheet:
        return self._get_spreadsheet().worksheet(title)

    def _get_lessons_sync(self) -> list[dict[str, Any]]:
        worksheet = self._worksheet(LESSONS_SHEET)
        records = worksheet.get_all_records()
        lessons: list[dict[str, Any]] = []
        for record in records:
            lesson_number = _to_int(record.get("lesson_number"))
            if lesson_number <= 0:
                continue
            lessons.append(
                {
                    "lesson_number": lesson_number,
                    "title": str(record.get("title", "")).strip(),
                    "text": str(record.get("text", "")).strip(),
                    "video_file_id": str(record.get("video_file_id", "")).strip(),
                    "document_file_id": str(record.get("document_file_id", "")).strip(),
                    "delay_hours": _to_float(record.get("delay_hours"), 24) or 24,
                    "active": _to_bool(record.get("active")),
                }
            )
        lessons.sort(key=lambda item: item["lesson_number"])
        return lessons

    def _get_users_sync(self) -> list[dict[str, Any]]:
        worksheet = self._worksheet(USERS_SHEET)
        records = worksheet.get_all_records()
        users: list[dict[str, Any]] = []
        for index, record in enumerate(records, start=2):
            telegram_id = _to_int(record.get("telegram_id"))
            if telegram_id <= 0:
                continue
            users.append(
                {
                    "_row": index,
                    "telegram_id": telegram_id,
                    "username": str(record.get("username", "")).strip(),
                    "first_name": str(record.get("first_name", "")).strip(),
                    "registered_at": str_to_datetime(str(record.get("registered_at", "")).strip()),
                    "current_lesson": _to_int(record.get("current_lesson")),
                    "last_lesson_sent_at": str_to_datetime(str(record.get("last_lesson_sent_at", "")).strip()),
                    "next_lesson_at": str_to_datetime(str(record.get("next_lesson_at", "")).strip()),
                    "status": str(record.get("status", "active")).strip() or "active",
                }
            )
        return users

    def _find_user_sync(self, telegram_id: int) -> dict[str, Any] | None:
        users = self._get_users_sync()
        for user in users:
            if user["telegram_id"] == telegram_id:
                return user
        return None

    def _add_user_sync(self, user_data: dict[str, Any]) -> None:
        worksheet = self._worksheet(USERS_SHEET)
        row = []
        for header in USERS_HEADERS:
            value = user_data.get(header, "")
            if isinstance(value, datetime):
                value = datetime_to_str(value)
            row.append(value)
        worksheet.append_row(row, value_input_option="USER_ENTERED")

    def _update_user_sync(self, telegram_id: int, updates: dict[str, Any]) -> None:
        users = self._get_users_sync()
        target_user = next((user for user in users if user["telegram_id"] == telegram_id), None)
        if not target_user:
            raise ValueError(f"User {telegram_id} not found in Users sheet")

        worksheet = self._worksheet(USERS_SHEET)
        row_values = [
            telegram_id,
            target_user["username"],
            target_user["first_name"],
            datetime_to_str(target_user["registered_at"]),
            target_user["current_lesson"],
            datetime_to_str(target_user["last_lesson_sent_at"]),
            datetime_to_str(target_user["next_lesson_at"]),
            target_user["status"],
        ]
        header_index = {name: idx for idx, name in enumerate(USERS_HEADERS)}

        for key, value in updates.items():
            if key not in header_index:
                continue
            if isinstance(value, datetime):
                value = datetime_to_str(value)
            elif value is None:
                value = ""
            row_values[header_index[key]] = value

        start_cell = f"A{target_user['_row']}:H{target_user['_row']}"
        worksheet.update(values=[row_values], range_name=start_cell, value_input_option="USER_ENTERED")

    def _update_statistics_sync(self) -> None:
        users = self._get_users_sync()
        total_users = len(users)
        status_counter = Counter(user["status"] for user in users)
        lesson_counter = Counter(user["current_lesson"] for user in users if user["current_lesson"] > 0)

        rows = [
            STATISTICS_HEADERS,
            ["total_users", total_users],
            ["active_users", status_counter.get("active", 0)],
            ["completed_users", status_counter.get("completed", 0)],
            ["blocked_users", status_counter.get("blocked", 0)],
        ]
        for lesson_number in sorted(lesson_counter):
            rows.append([f"lesson_{lesson_number}", lesson_counter[lesson_number]])

        worksheet = self._worksheet(STATISTICS_SHEET)
        worksheet.clear()
        worksheet.update(values=rows, range_name=f"A1:B{len(rows)}", value_input_option="USER_ENTERED")

    def _get_payments_sync(self) -> list[dict[str, Any]]:
        worksheet = self._worksheet(PAYMENTS_SHEET)
        records = worksheet.get_all_records()
        payments: list[dict[str, Any]] = []
        for index, record in enumerate(records, start=2):
            order_id = str(record.get("order_id", "")).strip()
            if not order_id:
                continue
            payments.append(
                {
                    "_row": index,
                    "order_id": order_id,
                    "telegram_id": _to_int(record.get("telegram_id")),
                    "username": str(record.get("username", "")).strip(),
                    "first_name": str(record.get("first_name", "")).strip(),
                    "amount": str(record.get("amount", "")).strip(),
                    "currency": str(record.get("currency", "")).strip(),
                    "status": str(record.get("status", "")).strip(),
                    "created_at": str(record.get("created_at", "")).strip(),
                    "paid_at": str(record.get("paid_at", "")).strip(),
                    "liqpay_payment_id": str(record.get("liqpay_payment_id", "")).strip(),
                    "raw_status": str(record.get("raw_status", "")).strip(),
                }
            )
        return payments

    def _add_payment_sync(self, payment_data: dict[str, Any]) -> None:
        worksheet = self._worksheet(PAYMENTS_SHEET)
        row = []
        for header in PAYMENTS_HEADERS:
            value = payment_data.get(header, "")
            if isinstance(value, datetime):
                value = datetime_to_str(value)
            row.append(value)
        worksheet.append_row(row, value_input_option="USER_ENTERED")

    def _find_payment_sync(self, order_id: str) -> dict[str, Any] | None:
        payments = self._get_payments_sync()
        for payment in payments:
            if payment["order_id"] == order_id:
                return payment
        return None

    def _update_payment_sync(self, order_id: str, updates: dict[str, Any]) -> None:
        payment = self._find_payment_sync(order_id)
        if not payment:
            raise ValueError(f"Payment {order_id} not found in Payments sheet")

        worksheet = self._worksheet(PAYMENTS_SHEET)
        row_values = [payment.get(header, "") for header in PAYMENTS_HEADERS]
        header_index = {name: idx for idx, name in enumerate(PAYMENTS_HEADERS)}

        for key, value in updates.items():
            if key not in header_index:
                continue
            if isinstance(value, datetime):
                value = datetime_to_str(value)
            elif value is None:
                value = ""
            row_values[header_index[key]] = value

        start_cell = f"A{payment['_row']}:K{payment['_row']}"
        worksheet.update(values=[row_values], range_name=start_cell, value_input_option="USER_ENTERED")
