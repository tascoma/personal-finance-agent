import logging
from datetime import date

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

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


agent = Agent(
    AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    ),
    output_type=ExtractedStatement,
    system_prompt=SYSTEM_PROMPT,
)


async def run_statement_extractor(text: str) -> ExtractedStatement:
    logger.debug("Running statement extractor (text length=%d)", len(text))
    try:
        result = await agent.run(text)
    except Exception:
        logger.exception("Statement extractor failed")
        raise
    logger.debug("Statement extractor succeeded: %d transaction(s) extracted", len(result.output.transactions))
    return result.output
