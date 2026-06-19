from __future__ import annotations

import csv
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.settings import get_settings
from app.models import Job, Transaction
from app.schemas.job import JobListItem, JobResult, JobStatusResponse, JobUploadResponse
from app.tasks import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _validate_upload(file: UploadFile) -> None:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported")


@router.post("/upload", response_model=JobUploadResponse)
def upload_job(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> JobUploadResponse:
    _validate_upload(file)
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    job = Job(filename=file.filename, source_path="", status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    destination = upload_dir / f"job_{job.id}_{file.filename}"
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    with destination.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        required = {
            "txn_id",
            "date",
            "merchant",
            "amount",
            "currency",
            "status",
            "category",
            "account_id",
            "notes",
        }
        if not required.issubset(set(fieldnames)):
            db.delete(job)
            db.commit()
            raise HTTPException(
                status_code=400, detail="CSV is missing one or more required columns"
            )

    job.source_path = str(destination)
    db.commit()

    process_job.delay(job.id)
    return JobUploadResponse(job_id=job.id, status=job.status)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    summary = None
    if job.status == "completed" and job.summary:
        summary = {
            "row_count_raw": job.row_count_raw,
            "row_count_clean": job.row_count_clean,
            "anomaly_count": job.summary.anomaly_count,
            "risk_level": job.summary.risk_level,
            "top_merchants": job.summary.top_merchants,
            "llm_failed_batches": job.summary.llm_failed_batches,
        }

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        summary=summary,
        error_message=job.error_message,
    )


@router.get("/{job_id}/results", response_model=JobResult)
def job_results(job_id: int, db: Session = Depends(get_db)) -> JobResult:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed yet")

    transactions = (
        db.query(Transaction)
        .filter(Transaction.job_id == job.id)
        .order_by(Transaction.row_index.asc())
        .all()
    )
    summary = job.summary
    if not summary:
        raise HTTPException(status_code=404, detail="Job summary not found")

    transaction_payload = [
        {
            "txn_id": transaction.txn_id,
            "date": transaction.date.isoformat() if transaction.date else None,
            "merchant": transaction.merchant,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
            "status": transaction.status,
            "category": transaction.category,
            "account_id": transaction.account_id,
            "notes": transaction.notes,
            "is_anomaly": transaction.is_anomaly,
            "anomaly_reason": transaction.anomaly_reason,
            "llm_category": transaction.llm_category,
            "llm_failed": transaction.llm_failed,
        }
        for transaction in transactions
    ]
    anomalies = [row for row in transaction_payload if row["is_anomaly"]]
    spend_breakdown = (
        summary.summary_payload.get("spend_breakdown", {})
        if summary.summary_payload
        else {}
    )

    return JobResult(
        job_id=job.id,
        status=job.status,
        summary={
            "total_spend_inr": summary.total_spend_inr,
            "total_spend_usd": summary.total_spend_usd,
            "top_merchants": summary.top_merchants,
            "anomaly_count": summary.anomaly_count,
            "narrative": summary.narrative,
            "risk_level": summary.risk_level,
            "llm_failed_batches": summary.llm_failed_batches,
        },
        transactions=transaction_payload,
        anomalies=anomalies,
        spend_breakdown=spend_breakdown,
    )


@router.get("")
def list_jobs(
    status: str | None = Query(default=None), db: Session = Depends(get_db)
) -> list[JobListItem]:
    query = db.query(Job).order_by(Job.created_at.desc())
    if status:
        query = query.filter(Job.status == status)
    jobs = query.all()
    return [JobListItem.model_validate(job) for job in jobs]
