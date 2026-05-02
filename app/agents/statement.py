"""Statement extractor agent.

For PDF bank/credit-card/investment statements where the row layout is unstructured.
CSV/XLSX statements are handled deterministically by `app.services.statement_mapper`
and never reach this agent.
"""

from datetime import date
from functools import lru_cache

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings


SYSTEM_PROMPT = (
    "You extract transaction rows from a bank or credit card statement. "
    "Return one row per posted transaction. Skip running balances, headers, "
    "summaries, and pending transactions. Sign amounts: deposits/credits are "
    "positive, withdrawals/charges are negative. Dates use the statement "
    "period's year if the row only shows MM/DD."
)


class ExtractedTxn(BaseModel):
    txn_date: date
    description: str
    amount: float  # signed: positive = money in, negative = money out


class ExtractedStatement(BaseModel):
    transactions: list[ExtractedTxn]


@lru_cache(maxsize=1)
def build_statement_extractor() -> Agent:
    """Build the statement extractor lazily.

    Constructed on first call so test environments without ``ANTHROPIC_API_KEY``
    can still import this module — they override ``get_statement_extractor``
    via FastAPI dependency overrides before any real call happens.
    """
    model = AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    )
    return Agent(
        model,
        output_type=ExtractedStatement,
        system_prompt=SYSTEM_PROMPT,
    )
