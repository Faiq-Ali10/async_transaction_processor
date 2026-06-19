from __future__ import annotations

from collections import Counter, defaultdict


def build_spend_breakdown(rows: list[dict]) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        category = row.get("effective_category") or row.get("category") or "Other"
        totals[category] += float(row["amount"])
    return dict(sorted(totals.items()))


def build_top_merchants(rows: list[dict], limit: int = 3) -> list[dict]:
    counter = Counter()
    for row in rows:
        counter[row["merchant"]] += float(row["amount"])
    return [
        {"merchant": merchant, "spend": round(amount, 2)}
        for merchant, amount in counter.most_common(limit)
    ]


def build_local_summary(rows: list[dict], anomaly_count: int) -> dict:
    by_currency: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        by_currency[row["currency"]] += float(row["amount"])

    return {
        "total_spend_by_currency": {
            currency: round(amount, 2) for currency, amount in by_currency.items()
        },
        "top_3_merchants": build_top_merchants(rows),
        "anomaly_count": anomaly_count,
        "narrative": "Spending is concentrated among a small set of merchants, with a mix of successful, failed, and pending transactions. A few rows are flagged as outliers or currency-merchant mismatches, indicating data quality and risk concerns.",
        "risk_level": "medium" if anomaly_count else "low",
    }
