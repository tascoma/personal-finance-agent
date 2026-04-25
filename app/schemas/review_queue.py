import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ReviewQueueRead(BaseModel):
    review_id: uuid.UUID
    period_id: uuid.UUID
    raw_txn_id: uuid.UUID
    review_type: str
    llm_suggestion: Optional[Any]
    llm_reasoning: Optional[str]
    user_decision: Optional[str]
    resolved_account_code: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewQueueResolve(BaseModel):
    user_decision: str
    resolved_account_code: Optional[int] = None
