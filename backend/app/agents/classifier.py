import logging
from decimal import Decimal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
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
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str


class ClassifierOutput(BaseModel):
    suggestions: list[TxnSuggestion]


agent = Agent(
    AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    ),
    output_type=ClassifierOutput,
    system_prompt=SYSTEM_PROMPT,
)


async def run_classifier(user_prompt: str) -> ClassifierOutput:
    logger.debug("Running classifier")
    try:
        result = await agent.run(user_prompt)
    except Exception:
        logger.exception("Classifier failed")
        raise
    logger.debug("Classifier succeeded: %d suggestion(s)", len(result.output.suggestions))
    return result.output
