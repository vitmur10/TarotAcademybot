from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_config
from app.google_sheets import GoogleSheetsClient
from app.handlers.admin import get_admin_router
from app.handlers.course import get_course_router
from app.handlers.start import get_start_router
from app.liqpay import LiqPayClient
from app.lessons import LessonManager
from app.payment_web import create_payment_app, start_payment_web_server
from app.payments import PaymentManager
from app.worker import lesson_worker


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    sheets = GoogleSheetsClient(
        spreadsheet_id=config.google_spreadsheet_id,
        credentials_file=config.google_credentials_file,
        timezone=config.timezone,
    )
    lesson_manager = LessonManager(sheets)
    payment_runner = None
    payment_manager = None

    if config.liqpay.enabled:
        liqpay = LiqPayClient(config.liqpay)
        payment_manager = PaymentManager(sheets=sheets, liqpay=liqpay, lesson_manager=lesson_manager)
        payment_app = create_payment_app(bot=bot, payment_manager=payment_manager)
        payment_runner = await start_payment_web_server(
            app=payment_app,
            host=config.liqpay.web_host,
            port=config.liqpay.web_port,
        )

    dp.include_router(get_start_router(lesson_manager, sheets, payment_manager, config.support_username))
    dp.include_router(get_course_router(sheets, lesson_manager))
    dp.include_router(get_admin_router(sheets, config.admin_ids))

    await sheets.update_statistics()
    worker_task = asyncio.create_task(
        lesson_worker(
            bot=bot,
            sheets=sheets,
            lesson_manager=lesson_manager,
            interval_seconds=config.lesson_check_interval,
        )
    )

    try:
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        if payment_runner:
            await payment_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
