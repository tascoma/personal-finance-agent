import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class MemoBalanceCreate(BaseModel):
    period_id: uuid.UUID
    account_code: int
    balance: Decimal
    units: Optional[Decimal] = None
    note: Optional[str] = None


class MemoBalanceRead(BaseModel):
    memo_id: uuid.UUID
    period_id: uuid.UUID
    account_code: int
    balance: Decimal
    units: Optional[Decimal]
    note: Optional[str]
    entered_at: datetime

    model_config = {"from_attributes": True}
