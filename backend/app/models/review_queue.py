import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.databases import Base


class ReviewQueue(Base):
    __tablename__ = "review_queue"
    __table_args__ = (
        CheckConstraint(
            "review_type IN ('unclassified', 'ambiguous', 'adjusting')",
            name="ck_review_type",
        ),
        CheckConstraint(
            "user_decision IS NULL OR user_decision IN ('approved', 'overridden', 'skipped')",
            name="ck_user_decision",
        ),
        Index("ix_review_queue_pending", "user_decision", sqlite_where=text("user_decision IS NULL")),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("periods.period_id"), nullable=False
    )
    raw_txn_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("raw_transactions.raw_txn_id"), nullable=False
    )
    review_type: Mapped[str] = mapped_column(String, nullable=False)
    llm_suggestion: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_decision: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolved_account_code: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("accounts.account_code"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
