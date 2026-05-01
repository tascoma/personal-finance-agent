import logging
from decimal import Decimal
from functools import lru_cache

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
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


@lru_cache(maxsize=1)
def build_reconciliation_agent() -> Agent:
    """Cached so the module can be imported in tests without a live API key."""
    model = AnthropicModel(
        "claude-sonnet-4-6",
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    )
    return Agent(model, output_type=ReconciliationAnalysis, system_prompt=_SYSTEM_PROMPT)
