"""Paystub extractor agent.

The agent extracts the literal payroll labels and classifies each line.
CoA mapping happens deterministically in `app.services.parse` using the
seeded `Account.paystub_mapping` field.
"""

from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

PAYSTUB_AGENT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "Extract ALL pay periods found in the document — some paystubs include "
    "more than one period (e.g. current period on page 1, prior period on page 2). "
    "For each period, preserve the exact payroll labels "
    "(e.g. 'REGULAR EARNING', 'ROTH 401K', 'INS MED U PT', 'FEDERAL TAX'). "
    "Classify each line as earning, deduction, tax, or net_pay. Do not sum "
    "or transform amounts."
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


@lru_cache(maxsize=1)
def build_paystub_extractor() -> Agent:
    """Build the paystub extractor lazily; see `statement.build_statement_extractor`."""
    model = AnthropicModel(
        PAYSTUB_AGENT_MODEL,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    )
    return Agent(
        model,
        output_type=ExtractedPaystubs,
        system_prompt=SYSTEM_PROMPT,
    )
