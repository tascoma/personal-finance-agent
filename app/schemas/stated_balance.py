import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class StatedBalanceCreate(BaseModel):
    period_id: uuid.UUID
    account_code: int
    stated_balance: Decimal


class StatedBalanceRead(BaseModel):
    balance_id: uuid.UUID
    period_id: uuid.UUID
    account_code: int
    stated_balance: Decimal
    entered_at: datetime

    model_config = {"from_attributes": True}
