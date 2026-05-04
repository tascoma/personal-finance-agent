from typing import Optional

from pydantic import BaseModel


class AccountRead(BaseModel):
    account_code: int
    account_name: str
    account_type: str
    sub_category: str
    normal_balance: str
    paystub_mapping: Optional[str]
    is_memo: bool
    is_active: bool

    model_config = {"from_attributes": True}
