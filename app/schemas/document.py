import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    period_id: uuid.UUID
    document_type: str
    file_name: str
    file_path: str
    source_account_code: Optional[int] = None


class DocumentRead(BaseModel):
    document_id: uuid.UUID
    period_id: uuid.UUID
    document_type: str
    file_name: str
    file_path: str
    source_account_code: Optional[int]
    parse_status: str
    parsed_at: Optional[datetime]
    llm_model: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
