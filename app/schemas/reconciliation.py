import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReconciliationRead(BaseModel):
    recon_id: uuid.UUID
    period_id: uuid.UUID
    account_code: int
    computed_balance: Decimal
    stated_balance: Decimal
    gap: Decimal
    status: str
    run_at: datetime

    model_config = {"from_attributes": True}
