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


class ReconciliationDetail(BaseModel):
    """Presentation-layer schema: combines DB row with computed breakdown and account metadata."""

    recon_id: uuid.UUID
    period_id: uuid.UUID
    account_code: int
    account_name: str
    is_investment: bool
    beginning_balance: Decimal
    period_net_change: Decimal
    computed_balance: Decimal
    stated_balance: Decimal
    gap: Decimal
    status: str
    run_at: datetime


class TempAccountLine(BaseModel):
    account_code: int
    account_name: str
    account_type: str      # "Income" or "Expense"
    sub_category: str
    normal_balance: str    # "debit" or "credit"
    period_balance: Decimal


class TempAccountPreview(BaseModel):
    income_accounts: list[TempAccountLine]
    expense_accounts: list[TempAccountLine]
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal    # negative = net loss
    closing_posted: bool


class EquityRollupPreview(BaseModel):
    net_income_balance: Decimal   # 300103 current-period balance; negative = net loss
    rollup_posted: bool
