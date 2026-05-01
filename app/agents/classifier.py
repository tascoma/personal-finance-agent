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
    "You are a personal finance bookkeeper. Given a list of bank or credit-card "
    "transactions and a chart of accounts, classify each transaction into the most "
    "appropriate account. Source account type matters: for an Asset source (e.g. "
    "checking), positive amounts are inflows (income or transfer in), negative "
    "amounts are outflows (expenses or payments out). For a Liability source (e.g. "
    "credit card), negative amounts are charges (typically expenses), positive "
    "amounts are payments or refunds. Return exactly one classification per "
    "transaction using only account_codes present in the chart of accounts. "
    "Set confidence between 0 and 1. Write reasoning as a single short sentence."
)


class TxnInput(BaseModel):
    id: str                   # raw_txn_id.hex[:8]
    description: str
    amount: Decimal
    source_account_name: str
    source_account_type: str  # e.g. "Asset", "Liability"


class TxnSuggestion(BaseModel):
    id: str
    account_code: int
    confidence: float
    reasoning: str


class ClassifierOutput(BaseModel):
    suggestions: list[TxnSuggestion]


@lru_cache(maxsize=1)
def build_classifier_agent() -> Agent:
    """Cached so the module can be imported in tests without an API key."""
    model = AnthropicModel(
        "claude-sonnet-4-6",
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    )
    return Agent(model, output_type=ClassifierOutput, system_prompt=_SYSTEM_PROMPT)
