from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.google_sheets import GoogleSheetsClient
from app.keyboards import broadcast_confirm_keyboard

LOGGER = logging.getLogger(__name__)


class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirm = State()


def get_admin_router(sheets: GoogleSheetsClient, admin_ids: set[int]) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in admin_ids

    @router.message(Command("broadcast"))
    async def broadcast_command(message: Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Команда доступна тільки адміністратору.")
            return
        await state.set_state(BroadcastState.waiting_for_text)
        await message.answer("Надішліть текст розсилки.")

    @router.message(Command("video_id"))
    async def video_id_command(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer("Команда доступна тільки адміністратору.")
            return
        await message.answer("Надішліть відео сюди, і я відповім його file_id.")

    @router.message(F.video)
    async def video_file_id_received(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return
        await message.answer(
            "video_file_id:\n"
            f"<code>{message.video.file_id}</code>",
            parse_mode="HTML",
            reply_to_message_id=message.message_id,
        )

    @router.message(F.document)
    async def document_file_id_received(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return
        await message.answer(
            "document_file_id:\n"
            f"<code>{message.document.file_id}</code>",
            parse_mode="HTML",
            reply_to_message_id=message.message_id,
        )

    @router.message(BroadcastState.waiting_for_text)
    async def broadcast_text_received(message: Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id):
            await state.clear()
            return
        if not message.text:
            await message.answer("Потрібен саме текстовий текст розсилки.")
            return

        await state.update_data(broadcast_text=message.text)
        await state.set_state(BroadcastState.waiting_for_confirm)
        await message.answer(
            f"Підтвердити розсилку?\n\n{message.text}",
            reply_markup=broadcast_confirm_keyboard(),
        )

    @router.callback_query(BroadcastState.waiting_for_confirm, F.data == "broadcast:cancel")
    async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.edit_text("Розсилку скасовано.")
        await callback.answer()

    @router.callback_query(BroadcastState.waiting_for_confirm, F.data == "broadcast:confirm")
    async def broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id):
            await state.clear()
            await callback.answer()
            return

        data = await state.get_data()
        text = data.get("broadcast_text", "").strip()
        await state.clear()

        if not text:
            await callback.message.edit_text("Текст розсилки відсутній.")
            await callback.answer()
            return

        await callback.message.edit_text("Розсилка запущена.")
        users = await sheets.get_users()
        recipients = [user for user in users if user["status"] != "blocked"]

        success_count = 0
        error_count = 0

        for user in recipients:
            try:
                await callback.bot.send_message(user["telegram_id"], text)
                success_count += 1
                await asyncio.sleep(0.05)
            except TelegramForbiddenError:
                error_count += 1
                await sheets.update_user(user["telegram_id"], {"status": "blocked", "next_lesson_at": None})
            except TelegramNetworkError as error:
                LOGGER.warning("Temporary error during broadcast for %s: %s", user["telegram_id"], error)
                error_count += 1
            except Exception:
                LOGGER.exception("Unexpected broadcast error for %s", user["telegram_id"])
                error_count += 1

        await sheets.update_statistics()
        await callback.message.answer(
            f"Розсилку завершено.\nУспішно: {success_count}\nПомилок: {error_count}"
        )
        await callback.answer()

    return router
