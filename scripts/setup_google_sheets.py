from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import load_config
from app.google_sheets import (  # noqa: E402
    LESSONS_HEADERS,
    LESSONS_SHEET,
    PAYMENTS_HEADERS,
    PAYMENTS_SHEET,
    STATISTICS_HEADERS,
    STATISTICS_SHEET,
    USERS_HEADERS,
    USERS_SHEET,
    GoogleSheetsClient,
)


def ensure_sheet(spreadsheet, title: str, headers: list[str]) -> None:
    try:
        worksheet = spreadsheet.worksheet(title)
    except Exception:
        worksheet = spreadsheet.add_worksheet(title=title, rows=100, cols=max(len(headers), 2))

    existing_headers = worksheet.row_values(1)
    if not existing_headers:
        worksheet.update(values=[headers], range_name="A1", value_input_option="USER_ENTERED")


def main() -> None:
    config = load_config()
    sheets = GoogleSheetsClient(
        spreadsheet_id=config.google_spreadsheet_id,
        credentials_file=config.google_credentials_file,
        timezone=config.timezone,
    )
    spreadsheet = sheets._get_spreadsheet()

    ensure_sheet(spreadsheet, LESSONS_SHEET, LESSONS_HEADERS)
    ensure_sheet(spreadsheet, USERS_SHEET, USERS_HEADERS)
    ensure_sheet(spreadsheet, STATISTICS_SHEET, STATISTICS_HEADERS)
    ensure_sheet(spreadsheet, PAYMENTS_SHEET, PAYMENTS_HEADERS)

    print("Google Sheets setup completed.")


if __name__ == "__main__":
    main()
