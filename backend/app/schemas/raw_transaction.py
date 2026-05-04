import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class RawTransactionRead(BaseModel):
    raw_txn_id: uuid.UUID
    document_id: uuid.UUID
    period_id: uuid.UUID
    txn_date: date
    description: str
    amount: Decimal
    suggested_account_code: Optional[int]
    classifier_confidence: Optional[Decimal]
    is_flagged: bool
    is_duplicate: bool
    dedup_hash: Optional[str]
    status: str
    journal_entry_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}
