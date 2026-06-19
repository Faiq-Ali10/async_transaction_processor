from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

REQUIRED_COLUMNS = [
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes",
]


def read_csv_rows(file_path: str | Path) -> list[dict[str, str]]:
    with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for pattern in ("%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def parse_amount(value: str | None) -> float:
    if value is None:
        raise ValueError("Amount is required")
    cleaned = re.sub(r"[^0-9.-]", "", value.strip())
    if not cleaned:
        raise ValueError("Amount is empty")
    return round(float(cleaned), 2)


def clean_text(value: str | None, *, default: str = "") -> str:
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def clean_row(row: dict[str, str], row_index: int) -> dict:
    merchant = clean_text(row.get("merchant"))
    return {
        "row_index": row_index,
        "txn_id": clean_text(row.get("txn_id")) or None,
        "date": parse_date(row.get("date")),
        "merchant": merchant,
        "merchant_key": merchant.upper(),
        "amount": parse_amount(row.get("amount")),
        "currency": clean_text(row.get("currency")).upper(),
        "status": clean_text(row.get("status")).upper(),
        "category": clean_text(row.get("category"), default="Uncategorised")
        or "Uncategorised",
        "account_id": clean_text(row.get("account_id")),
        "notes": clean_text(row.get("notes")) or None,
        "raw_payload": row,
    }


def deduplicate_rows(rows: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    unique_rows: list[dict] = []
    for row in rows:
        fingerprint = hashlib.sha256(
            repr(sorted(row.items())).encode("utf-8")
        ).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique_rows.append(row)
    return unique_rows
