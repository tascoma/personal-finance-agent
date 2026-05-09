from decimal import Decimal

from pydantic import BaseModel

from app.agents._base import build_agent, run_agent

SYSTEM_PROMPT = (
    "You are a personal finance bookkeeper reviewing monthly reconciliation gaps. "
    "For each account with a non-zero gap between the computed book balance and the "
    "user-stated balance, identify the most likely causes and suggest concrete next steps. "
    "Consider: missing transactions not yet entered, duplicate entries, incorrect account "
    "classifications, timing differences (outstanding checks, in-transit deposits), or "
    "data-entry errors in the stated balance. Be specific and concise. "
    "Note: investment account gaps due to unrealized market gains or losses are handled "
    "separately and will NOT appear in this list."
)


class AccountGap(BaseModel):
    account_code: int
    account_name: str
    computed_balance: Decimal
    stated_balance: Decimal
    gap: Decimal
    recent_entry_descriptions: list[str]


class AccountAnalysis(BaseModel):
    account_code: int
    likely_causes: list[str]
    suggested_actions: list[str]
    severity: str  # 'low' | 'medium' | 'high'


class ReconciliationAnalysis(BaseModel):
    accounts: list[AccountAnalysis]
    overall_summary: str


agent = build_agent(ReconciliationAnalysis, SYSTEM_PROMPT)


async def run_reconciliation_agent(gaps: list[AccountGap]) -> ReconciliationAnalysis:
    return await run_agent(agent, "reconciliation agent", gaps)
