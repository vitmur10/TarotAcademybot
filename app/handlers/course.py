from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.google_sheets import GoogleSheetsClient
from app.lessons import LessonManager


def _format_next_lesson(value) -> str:
    if not value:
        return "не заплановано"
    return value.strftime("%d.%m о %H:%M")


def get_course_router(sheets: GoogleSheetsClient, lesson_manager: LessonManager) -> Router:
    router = Router()

    @router.message(F.text == "📚 Мій курс")
    async def my_course_handler(message: Message) -> None:
        user = await sheets.find_user(message.from_user.id)
        if not user:
            await message.answer("Курс ще не розпочато. Натисніть /start.")
            return

        total_lessons = await lesson_manager.get_total_active_lessons()
        completed_lessons = await lesson_manager.get_completed_active_lessons_count(user["current_lesson"])
        if user["status"] == "completed":
            await message.answer("✅ Курс завершено")
            return

        await message.answer(
            f"Поточний урок: {completed_lessons} із {total_lessons}\n\n"
            f"Наступний урок:\n{_format_next_lesson(user['next_lesson_at'])}"
        )

    @router.message(F.text == "📊 Мій прогрес")
    async def my_progress_handler(message: Message) -> None:
        user = await sheets.find_user(message.from_user.id)
        if not user:
            await message.answer("Курс ще не розпочато. Натисніть /start.")
            return

        total_lessons = await lesson_manager.get_total_active_lessons()
        completed_lessons = await lesson_manager.get_completed_active_lessons_count(user["current_lesson"])
        progress = int((completed_lessons / total_lessons) * 100) if total_lessons else 0
        await message.answer(
            f"Пройдено: {completed_lessons} із {total_lessons} уроків\n"
            f"Прогрес: {progress}%"
        )

    return router
