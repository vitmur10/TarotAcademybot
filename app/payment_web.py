from __future__ import annotations

import logging

from aiohttp import web
from aiogram import Bot

from app.payments import PaymentManager

LOGGER = logging.getLogger(__name__)


def create_payment_app(bot: Bot, payment_manager: PaymentManager) -> web.Application:
    app = web.Application()

    async def pay_page(request: web.Request) -> web.Response:
        order_id = request.match_info["order_id"]
        checkout = await payment_manager.get_checkout(order_id)
        if not checkout:
            return web.Response(text="Payment not found", status=404)
        return web.Response(
            text=payment_manager.liqpay.render_checkout_page(checkout),
            content_type="text/html",
        )

    async def liqpay_callback(request: web.Request) -> web.Response:
        form = await request.post()
        data = str(form.get("data", ""))
        signature = str(form.get("signature", ""))
        if not data or not signature:
            return web.Response(text="missing data or signature", status=400)

        try:
            accepted = await payment_manager.process_callback(bot, data, signature)
        except Exception:
            LOGGER.exception("LiqPay callback processing failed")
            return web.Response(text="error", status=500)

        if not accepted:
            return web.Response(text="invalid", status=400)
        return web.Response(text="ok")

    async def payment_result(_: web.Request) -> web.Response:
        return web.Response(
            text=(
                "<!doctype html><html lang=\"uk\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>Оплата</title></head><body>"
                "<p>Дякуємо. Поверніться в Telegram, бот відкриє доступ після підтвердження платежу.</p>"
                "</body></html>"
            ),
            content_type="text/html",
        )

    app.router.add_get("/pay/{order_id}", pay_page)
    app.router.add_post("/liqpay/callback", liqpay_callback)
    app.router.add_get("/payment-result", payment_result)
    return app


async def start_payment_web_server(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    LOGGER.info("Payment web server started on %s:%s", host, port)
    return runner
