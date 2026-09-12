from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from html import escape
from typing import Any

from app.config import LiqPayConfig

LIQPAY_CHECKOUT_URL = "https://www.liqpay.ua/api/3/checkout"
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LiqPayCheckout:
    order_id: str
    data: str
    signature: str
    payment_page_url: str


class LiqPayClient:
    def __init__(self, config: LiqPayConfig) -> None:
        self.config = config

    def create_checkout(self, order_id: str, telegram_id: int) -> LiqPayCheckout:
        payload = {
            "version": 7,
            "public_key": self.config.public_key,
            "action": "pay",
            "amount": self.config.amount,
            "currency": self.config.currency,
            "description": self.config.description,
            "order_id": order_id,
            "language": "uk",
            "server_url": f"{self.config.public_base_url}/liqpay/callback",
            "result_url": self.config.result_url,
            "customer": str(telegram_id),
        }
        if self.config.sandbox:
            payload["sandbox"] = 1
        LOGGER.info(
            "Creating LiqPay checkout: order_id=%s public_key=%s sandbox=%s amount=%s currency=%s server_url=%s result_url=%s payment_page_url=%s",
            order_id,
            self.config.public_key,
            self.config.sandbox,
            self.config.amount,
            self.config.currency,
            payload["server_url"],
            payload["result_url"],
            f"{self.config.public_base_url}/pay/{order_id}",
        )
        data = self._encode_payload(payload)
        return LiqPayCheckout(
            order_id=order_id,
            data=data,
            signature=self.sign(data),
            payment_page_url=f"{self.config.public_base_url}/pay/{order_id}",
        )

    def sign(self, data: str) -> str:
        sign_string = f"{self.config.private_key}{data}{self.config.private_key}"
        digest = hashlib.sha1(sign_string.encode("utf-8")).digest()
        return base64.b64encode(digest).decode("ascii")

    def verify_signature(self, data: str, signature: str) -> bool:
        return self.sign(data) == signature

    def decode_data(self, data: str) -> dict[str, Any]:
        raw_json = base64.b64decode(data).decode("utf-8")
        decoded = json.loads(raw_json)
        if not isinstance(decoded, dict):
            raise ValueError("LiqPay data payload must be an object")
        return decoded

    def render_checkout_page(self, checkout: LiqPayCheckout) -> str:
        data = escape(checkout.data, quote=True)
        signature = escape(checkout.signature, quote=True)
        return (
            "<!doctype html>"
            "<html lang=\"uk\">"
            "<head>"
            "<meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Оплата курсу</title>"
            "<style>"
            "body{font-family:Arial,sans-serif;margin:0;min-height:100vh;display:grid;place-items:center;background:#f6f7f9;color:#15171a}"
            "main{max-width:420px;padding:32px;text-align:center}"
            "button{border:0;border-radius:8px;background:#1f8b4c;color:white;padding:14px 20px;font-size:16px;cursor:pointer}"
            "</style>"
            "</head>"
            "<body>"
            "<main>"
            "<h1>Переходимо до оплати</h1>"
            "<p>Якщо перехід не відбувся автоматично, натисніть кнопку нижче.</p>"
            f"<form id=\"liqpay\" method=\"POST\" action=\"{LIQPAY_CHECKOUT_URL}\" accept-charset=\"utf-8\">"
            f"<input type=\"hidden\" name=\"data\" value=\"{data}\">"
            f"<input type=\"hidden\" name=\"signature\" value=\"{signature}\">"
            "<button type=\"submit\">Оплатити через LiqPay</button>"
            "</form>"
            "</main>"
            "<script>document.getElementById('liqpay').submit();</script>"
            "</body>"
            "</html>"
        )

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        raw_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
