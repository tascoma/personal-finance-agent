import logging
from datetime import date
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Extract ALL pay periods found in the document — some paystubs include "
    "more than one period (e.g. current period on page 1, prior period on page 2). "
    "For each period, preserve the exact payroll labels "
    "(e.g. 'REGULAR EARNING', 'ROTH 401K', 'INS MED U PT', 'FEDERAL TAX'). "
    "Classify each line as earning, deduction, tax, or net_pay. Do not sum "
    "or transform amounts. Omit any line item whose amount is zero."
)


class PaystubLine(BaseModel):
    label: str
    amount: float
    kind: Literal["earning", "deduction", "tax", "net_pay"]


class ExtractedPaystub(BaseModel):
    pay_date: date
    lines: list[PaystubLine]
    gross_pay: float
    net_pay: float


class ExtractedPaystubs(BaseModel):
    paystubs: list[ExtractedPaystub]


agent = Agent(
    AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    ),
    output_type=ExtractedPaystubs,
    system_prompt=SYSTEM_PROMPT,
)


async def run_paystub_extractor(text: str) -> ExtractedPaystubs:
    logger.debug("Running paystub extractor (text length=%d)", len(text))
    try:
        result = await agent.run(text)
    except Exception:
        logger.exception("Paystub extractor failed")
        raise
    output = result.output
    for paystub in output.paystubs:
        paystub.lines = [line for line in paystub.lines if line.amount != 0]
    logger.debug("Paystub extractor succeeded: %d paystub(s) extracted", len(output.paystubs))
    return output
