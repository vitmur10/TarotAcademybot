from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class LiqPayConfig:
    enabled: bool
    sandbox: bool
    public_key: str
    private_key: str
    amount: float
    currency: str
    description: str
    public_base_url: str
    result_url: str
    web_host: str
    web_port: int


@dataclass(slots=True)
class ManualPaymentConfig:
    enabled: bool
    review_chat_id: int | None
    details: str


@dataclass(slots=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    support_username: str
    google_spreadsheet_id: str
    google_credentials_file: str
    timezone: ZoneInfo
    lesson_check_interval: int
    liqpay: LiqPayConfig
    manual_payment: ManualPaymentConfig


def _parse_admin_ids(raw_value: str) -> set[int]:
    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        item = item.strip()
        if item:
            admin_ids.add(int(item))
    return admin_ids


def _parse_bool(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_optional_int(raw_value: str) -> int | None:
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    return int(raw_value)


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip()
    timezone_name = os.getenv("TIMEZONE", "Europe/Kyiv").strip()
    lesson_check_interval = int(os.getenv("LESSON_CHECK_INTERVAL", "60"))
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    support_username = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")
    manual_payment_enabled = _parse_bool(os.getenv("MANUAL_PAYMENT_ENABLED", "false"))
    manual_payment_review_chat_id = _parse_optional_int(os.getenv("MANUAL_PAYMENT_REVIEW_CHAT_ID", ""))
    manual_payment_details = os.getenv("MANUAL_PAYMENT_DETAILS", "").strip().replace("\\n", "\n")
    liqpay_enabled = _parse_bool(os.getenv("LIQPAY_ENABLED", "false"))
    liqpay_sandbox = _parse_bool(os.getenv("LIQPAY_SANDBOX", "false"))
    liqpay_public_key = os.getenv("LIQPAY_PUBLIC_KEY", "").strip()
    liqpay_private_key = os.getenv("LIQPAY_PRIVATE_KEY", "").strip()
    liqpay_amount = float(os.getenv("LIQPAY_AMOUNT", "0") or "0")
    liqpay_currency = os.getenv("LIQPAY_CURRENCY", "UAH").strip().upper()
    liqpay_description = os.getenv("LIQPAY_DESCRIPTION", "Tarot Academy course").strip()
    liqpay_public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    liqpay_result_url = os.getenv("LIQPAY_RESULT_URL", "").strip()
    liqpay_web_host = os.getenv("PAYMENT_WEB_HOST", "0.0.0.0").strip()
    liqpay_web_port = int(os.getenv("PAYMENT_WEB_PORT", "8080"))

    if not bot_token:
        raise ValueError("BOT_TOKEN is required")
    if not spreadsheet_id:
        raise ValueError("GOOGLE_SPREADSHEET_ID is required")
    if manual_payment_enabled:
        if manual_payment_review_chat_id is None:
            raise ValueError("MANUAL_PAYMENT_REVIEW_CHAT_ID is required when MANUAL_PAYMENT_ENABLED=true")
        if not manual_payment_details:
            raise ValueError("MANUAL_PAYMENT_DETAILS is required when MANUAL_PAYMENT_ENABLED=true")
    if liqpay_enabled:
        if not liqpay_public_key:
            raise ValueError("LIQPAY_PUBLIC_KEY is required when LIQPAY_ENABLED=true")
        if not liqpay_private_key:
            raise ValueError("LIQPAY_PRIVATE_KEY is required when LIQPAY_ENABLED=true")
        if liqpay_amount <= 0:
            raise ValueError("LIQPAY_AMOUNT must be greater than 0 when LIQPAY_ENABLED=true")
        if not liqpay_public_base_url:
            raise ValueError("PUBLIC_BASE_URL is required when LIQPAY_ENABLED=true")
        if not liqpay_result_url:
            liqpay_result_url = f"{liqpay_public_base_url}/payment-result"

    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_file = str((PROJECT_ROOT / credentials_path).resolve())

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        support_username=support_username,
        google_spreadsheet_id=spreadsheet_id,
        google_credentials_file=credentials_file,
        timezone=ZoneInfo(timezone_name),
        lesson_check_interval=lesson_check_interval,
        liqpay=LiqPayConfig(
            enabled=liqpay_enabled,
            sandbox=liqpay_sandbox,
            public_key=liqpay_public_key,
            private_key=liqpay_private_key,
            amount=liqpay_amount,
            currency=liqpay_currency,
            description=liqpay_description,
            public_base_url=liqpay_public_base_url,
            result_url=liqpay_result_url,
            web_host=liqpay_web_host,
            web_port=liqpay_web_port,
        ),
        manual_payment=ManualPaymentConfig(
            enabled=manual_payment_enabled,
            review_chat_id=manual_payment_review_chat_id,
            details=manual_payment_details,
        ),
    )
