from __future__ import annotations

from collections import defaultdict
from statistics import median

DOMESTIC_ONLY_BRANDS = {"SWIGGY", "OLA", "IRCTC"}


def detect_anomalies(rows: list[dict]) -> list[dict]:
    account_amounts: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        account_amounts[row["account_id"]].append(float(row["amount"]))

    medians = {
        account_id: median(amounts)
        for account_id, amounts in account_amounts.items()
        if amounts
    }

    flagged_rows: list[dict] = []
    for row in rows:
        amount = float(row["amount"])
        account_median = medians.get(row["account_id"], 0)
        is_anomaly = False
        reasons: list[str] = []

        if account_median and amount > account_median * 3:
            is_anomaly = True
            reasons.append(f"Amount exceeds 3x account median ({account_median:.2f})")

        if (
            row["currency"].upper() == "USD"
            and row["merchant_key"] in DOMESTIC_ONLY_BRANDS
        ):
            is_anomaly = True
            reasons.append("USD currency used for domestic-only merchant")

        flagged_rows.append(
            {
                **row,
                "is_anomaly": is_anomaly,
                "anomaly_reason": "; ".join(reasons) if reasons else None,
            }
        )

    return flagged_rows
