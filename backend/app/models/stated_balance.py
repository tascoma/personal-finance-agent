import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.databases import Base


class StatedBalance(Base):
    __tablename__ = "stated_balances"
    __table_args__ = (
        UniqueConstraint("period_id", "account_code", name="uq_stated_balance_period_account"),
    )

    balance_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("periods.period_id"), nullable=False
    )
    account_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_code"), nullable=False
    )
    stated_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
