import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PeriodCreate(BaseModel):
    period_start: date
    period_end: date


class PeriodRead(BaseModel):
    period_id: uuid.UUID
    period_start: date
    period_end: date
    status: str
    closed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
