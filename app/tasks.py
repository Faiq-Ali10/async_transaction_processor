from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.settings import get_settings
from app.models import Job, JobSummary, Transaction
from app.services.anomaly import detect_anomalies
from app.services.csv_processor import clean_row, deduplicate_rows, read_csv_rows
from app.services.llm import GeminiClient, call_with_retry
from app.services.report import build_local_summary, build_spend_breakdown


def _ensure_directories() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.result_dir).mkdir(parents=True, exist_ok=True)


def _chunks(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat") and value.__class__.__name__ == "date":
        return value.isoformat()
    return value


def _fallback_category(row: dict) -> str:
    merchant = row["merchant_key"]
    notes = (row.get("notes") or "").upper()
    if any(
        keyword in merchant for keyword in ["SWIGGY", "ZOMATO", "UBER EATS", "FOOD"]
    ):
        return "Food"
    if any(keyword in merchant for keyword in ["AMAZON", "FLIPKART", "MYNTRA"]):
        return "Shopping"
    if any(keyword in merchant for keyword in ["IRCTC", "MAKEMYTRIP", "GOIBIBO"]):
        return "Travel"
    if any(keyword in merchant for keyword in ["OLA", "UBER", "METRO", "TAXI"]):
        return "Transport"
    if any(
        keyword in merchant
        for keyword in ["JIO", "AIRTEL", "BSNL", "ELECTRIC", "POWER"]
    ):
        return "Utilities"
    if "CASH WITHDRAWAL" in notes or merchant.endswith("ATM"):
        return "Cash Withdrawal"
    return "Other"


@celery_app.task(name="app.tasks.process_job")
def process_job(job_id: int) -> dict:
    _ensure_directories()
    settings = get_settings()
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "processing"
        job.error_message = None
        db.commit()

        raw_rows = read_csv_rows(job.source_path)
        cleaned_rows = [clean_row(row, index + 1) for index, row in enumerate(raw_rows)]
        cleaned_rows = deduplicate_rows(cleaned_rows)
        cleaned_rows = detect_anomalies(cleaned_rows)

        client = GeminiClient()
        missing_category_rows = [
            row
            for row in cleaned_rows
            if row["category"].upper() == "UNCATEGORISED" or not row["category"].strip()
        ]
        llm_failed_batches = 0
        category_lookup: dict[str, str] = {}

        for batch in _chunks(missing_category_rows, settings.llm_batch_size):
            try:
                response = call_with_retry(
                    lambda: client.classify_transactions(batch), retries=3
                )
                for item in response:
                    txn_key = str(item.get("txn_id") or "")
                    category = str(item.get("category") or "Other")
                    if txn_key:
                        category_lookup[txn_key] = category
            except Exception:
                llm_failed_batches += 1
                for row in batch:
                    row["llm_failed"] = True
                    category_lookup[str(row.get("txn_id") or row["row_index"])] = (
                        _fallback_category(row)
                    )

        enriched_rows: list[dict] = []
        for row in cleaned_rows:
            effective_category = row["category"]
            if (
                effective_category.upper() == "UNCATEGORISED"
                or not effective_category.strip()
            ):
                effective_category = category_lookup.get(
                    str(row.get("txn_id") or row["row_index"]), _fallback_category(row)
                )
            enriched_rows.append(
                {
                    **row,
                    "effective_category": effective_category,
                    "llm_failed": row.get("llm_failed", False),
                }
            )

        anomaly_count = sum(1 for row in enriched_rows if row["is_anomaly"])
        summary_payload = build_local_summary(
            enriched_rows, anomaly_count=anomaly_count
        )
        try:
            llm_summary = call_with_retry(
                lambda: client.narrative_summary(
                    {
                        "total_spend_by_currency": summary_payload[
                            "total_spend_by_currency"
                        ],
                        "top_3_merchants": summary_payload["top_3_merchants"],
                        "anomaly_count": summary_payload["anomaly_count"],
                        "narrative_hint": summary_payload["narrative"],
                    }
                ),
                retries=3,
            )
            summary_payload.update(llm_summary)
        except Exception:
            llm_failed_batches += 1

        spend_breakdown = build_spend_breakdown(enriched_rows)
        anomaly_rows = [
            {
                "txn_id": row.get("txn_id"),
                "merchant": row["merchant"],
                "amount": float(row["amount"]),
                "currency": row["currency"],
                "reason": row["anomaly_reason"],
            }
            for row in enriched_rows
            if row["is_anomaly"]
        ]

        job.row_count_raw = len(raw_rows)
        job.row_count_clean = len(enriched_rows)
        job.status = "completed"
        job.completed_at = datetime.utcnow()

        db.query(Transaction).filter(Transaction.job_id == job.id).delete()
        for row in enriched_rows:
            db.add(
                Transaction(
                    job_id=job.id,
                    row_index=row["row_index"],
                    txn_id=row["txn_id"],
                    date=row["date"],
                    merchant=row["merchant"],
                    amount=row["amount"],
                    currency=row["currency"],
                    status=row["status"],
                    category=row["category"],
                    account_id=row["account_id"],
                    notes=row["notes"],
                    is_anomaly=row["is_anomaly"],
                    anomaly_reason=row["anomaly_reason"],
                    llm_category=(
                        row["effective_category"]
                        if row["category"].upper() == "UNCATEGORISED"
                        else None
                    ),
                    llm_raw_response=_json_safe(summary_payload),
                    llm_failed=bool(row.get("llm_failed", False)),
                    raw_payload=_json_safe(row["raw_payload"]),
                    cleaned_payload=_json_safe(row),
                )
            )

        existing_summary = (
            db.query(JobSummary).filter(JobSummary.job_id == job.id).one_or_none()
        )
        if existing_summary:
            db.delete(existing_summary)
        db.add(
            JobSummary(
                job_id=job.id,
                total_spend_inr=float(
                    summary_payload.get("total_spend_by_currency", {}).get("INR", 0)
                ),
                total_spend_usd=float(
                    summary_payload.get("total_spend_by_currency", {}).get("USD", 0)
                ),
                top_merchants=summary_payload.get("top_3_merchants", []),
                anomaly_count=summary_payload.get("anomaly_count", 0),
                narrative=summary_payload.get("narrative", ""),
                risk_level=summary_payload.get("risk_level", "low"),
                llm_failed_batches=llm_failed_batches,
                summary_payload={
                    "summary": summary_payload,
                    "spend_breakdown": spend_breakdown,
                    "anomalies": anomaly_rows,
                },
            )
        )
        db.commit()

        return {
            "job_id": job.id,
            "status": job.status,
            "row_count_clean": job.row_count_clean,
        }
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()
