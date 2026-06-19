from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobSummary(Base):
    __tablename__ = "job_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    total_spend_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_spend_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    top_merchants: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    llm_failed_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    job = relationship("Job", back_populates="summary")
