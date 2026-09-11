from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from aiogram.types import User

from app.google_sheets import GoogleSheetsClient, now_in_timezone

LOGGER = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_VIDEO_CAPTION_LIMIT = 1024


@dataclass(slots=True)
class LessonSendResult:
    delivered: bool
    completed_course: bool = False
    blocked_user: bool = False


class LessonManager:
    def __init__(self, sheets: GoogleSheetsClient) -> None:
        self.sheets = sheets

    async def register_and_send_first_lesson(self, bot: Bot, telegram_user: User) -> LessonSendResult:
        existing_user = await self.sheets.find_user(telegram_user.id)
        if existing_user:
            if (
                existing_user["status"] == "active"
                and existing_user["current_lesson"] == 0
                and not existing_user["next_lesson_at"]
            ):
                return await self.send_next_lesson(bot, existing_user)
            return LessonSendResult(delivered=False, completed_course=existing_user["status"] == "completed")

        registered_at = now_in_timezone(self.sheets.timezone)
        await self.sheets.add_user(
            {
                "telegram_id": telegram_user.id,
                "username": telegram_user.username or "",
                "first_name": telegram_user.first_name or "",
                "registered_at": registered_at,
                "current_lesson": 0,
                "last_lesson_sent_at": "",
                "next_lesson_at": "",
                "status": "active",
            }
        )

        user = await self.sheets.find_user(telegram_user.id)
        if not user:
            raise RuntimeError("User was not created in Users sheet")
        return await self.send_next_lesson(bot, user)

    async def send_next_lesson(self, bot: Bot, user: dict[str, Any]) -> LessonSendResult:
        next_lesson = await self.get_next_active_lesson(user["current_lesson"])
        if not next_lesson:
            await self.sheets.update_user(
                user["telegram_id"],
                {"status": "completed", "next_lesson_at": None},
            )
            return LessonSendResult(delivered=False, completed_course=True)

        delivered = await self._send_lesson_content(bot, user["telegram_id"], next_lesson)
        if delivered.blocked_user or not delivered.delivered:
            return delivered

        sent_at = now_in_timezone(self.sheets.timezone)
        following_lesson = await self.get_next_active_lesson(next_lesson["lesson_number"])
        updates = {
            "current_lesson": next_lesson["lesson_number"],
            "last_lesson_sent_at": sent_at,
        }

        if following_lesson:
            updates["next_lesson_at"] = sent_at + timedelta(hours=following_lesson["delay_hours"])
            updates["status"] = "active"
            await self.sheets.update_user(user["telegram_id"], updates)
            return LessonSendResult(delivered=True)

        updates["next_lesson_at"] = None
        updates["status"] = "completed"
        await self.sheets.update_user(user["telegram_id"], updates)
        await bot.send_message(user["telegram_id"], "Вітаємо! Ви завершили курс 🎉")
        return LessonSendResult(delivered=True, completed_course=True)

    async def get_next_active_lesson(self, current_lesson_number: int) -> dict[str, Any] | None:
        lessons = await self.sheets.get_lessons()
        for lesson in lessons:
            if lesson["active"] and lesson["lesson_number"] > current_lesson_number:
                return lesson
        return None

    async def get_total_active_lessons(self) -> int:
        lessons = await self.sheets.get_lessons()
        return len([lesson for lesson in lessons if lesson["active"]])

    async def get_completed_active_lessons_count(self, current_lesson_number: int) -> int:
        lessons = await self.sheets.get_lessons()
        return len(
            [
                lesson
                for lesson in lessons
                if lesson["active"] and lesson["lesson_number"] <= current_lesson_number
            ]
        )

    async def _send_text_chunks(self, bot: Bot, chat_id: int, text: str) -> None:
        for start in range(0, len(text), TELEGRAM_MESSAGE_LIMIT):
            await bot.send_message(
                chat_id,
                text[start : start + TELEGRAM_MESSAGE_LIMIT],
                protect_content=True,
            )

    async def _send_lesson_content(self, bot: Bot, chat_id: int, lesson: dict[str, Any]) -> LessonSendResult:
        title = lesson["title"].strip()
        text = lesson["text"].strip()
        if title:
            header = f"Урок {lesson['lesson_number']}. {title}"
        else:
            header = f"Урок {lesson['lesson_number']}"
        full_text = "\n\n".join([item for item in [header, text] if item])

        try:
            if lesson["video_file_id"]:
                video_caption = full_text if len(full_text) <= TELEGRAM_VIDEO_CAPTION_LIMIT else header
                await bot.send_video(
                    chat_id,
                    video=lesson["video_file_id"],
                    caption=video_caption,
                    protect_content=True,
                )
                if full_text != video_caption and text:
                    await self._send_text_chunks(bot, chat_id, text)
            elif full_text:
                await self._send_text_chunks(bot, chat_id, full_text)

            if lesson["document_file_id"]:
                await bot.send_document(
                    chat_id,
                    document=lesson["document_file_id"],
                    protect_content=True,
                )
            return LessonSendResult(delivered=True)
        except TelegramForbiddenError:
            LOGGER.warning("User %s blocked the bot", chat_id)
            await self.sheets.update_user(chat_id, {"status": "blocked", "next_lesson_at": None})
            return LessonSendResult(delivered=False, blocked_user=True)
        except TelegramBadRequest as error:
            LOGGER.exception("Telegram rejected lesson %s for user %s: %s", lesson["lesson_number"], chat_id, error)
            return LessonSendResult(delivered=False)
        except TelegramNetworkError as error:
            LOGGER.warning("Temporary Telegram error for user %s: %s", chat_id, error)
            return LessonSendResult(delivered=False)
