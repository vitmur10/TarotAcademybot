from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot

from app.google_sheets import GoogleSheetsClient, now_in_timezone
from app.lessons import LessonManager

LOGGER = logging.getLogger(__name__)


async def lesson_worker(
    bot: Bot,
    sheets: GoogleSheetsClient,
    lesson_manager: LessonManager,
    interval_seconds: int,
) -> None:
    last_statistics_update = now_in_timezone(sheets.timezone) - timedelta(minutes=10)

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            current_time = now_in_timezone(sheets.timezone)
            users = await sheets.get_active_users()

            for user in users:
                next_lesson_at = user["next_lesson_at"]
                if not next_lesson_at or next_lesson_at > current_time:
                    continue
                await lesson_manager.send_next_lesson(bot, user)

            if current_time - last_statistics_update >= timedelta(minutes=5):
                await sheets.update_statistics()
                last_statistics_update = current_time
        except Exception:
            LOGGER.exception("Lesson worker iteration failed")
