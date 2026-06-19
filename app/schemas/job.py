from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobUploadResponse(BaseModel):
    job_id: int
    status: str


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    summary: dict | None = None
    error_message: str | None = None


class JobResult(BaseModel):
    job_id: int
    status: str
    summary: dict
    transactions: list[dict]
    anomalies: list[dict]
    spend_breakdown: dict[str, float]
