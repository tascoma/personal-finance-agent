"""Mortgage statement extractor agent.

Extracts the payment breakdown from a mortgage statement PDF: principal,
interest, and escrow components (property tax and home insurance).
Deterministic sign assignment and account mapping happen in
`app.services.parse` — this agent only returns the raw dollar amounts.
"""

from datetime import date
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

MORTGAGE_AGENT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "Extract the payment breakdown from a mortgage statement. "
    "Return the payment date and the exact positive dollar amount for each field:\n"
    "  • principal — the portion applied to reduce the outstanding loan balance\n"
    "  • interest — the borrowing cost charged for the period\n"
    "  • escrow — the total amount deposited into the escrow account this period "
    "(labelled 'escrow', 'escrow payment', or similar; this funds future tax and "
    "insurance bills but is NOT the same as paying them directly)\n"
    "  • property_tax — only when a property tax bill is actually disbursed/paid "
    "from escrow (appears on escrow analysis or disbursement statements, not on "
    "regular monthly payment statements); otherwise 0\n"
    "  • home_insurance — only when a homeowners insurance premium is actually "
    "disbursed/paid from escrow; otherwise 0\n"
    "On a regular monthly payment statement, escrow will be non-zero and "
    "property_tax and home_insurance will typically be 0. "
    "Never infer, compute, or total amounts — only return values explicitly shown."
)


class ExtractedMortgage(BaseModel):
    payment_date: date
    principal: float
    interest: float
    escrow: float = Field(description="The total escrow amount, which may include both property tax and home insurance. ")
    property_tax: float = Field(description="When property tax is payed out of the escrow account")
    home_insurance: float = Field(description="When home insurance is payed out of the escrow account")


@lru_cache(maxsize=1)
def build_mortgage_extractor() -> Agent:
    """Build the mortgage extractor lazily; see `statement.build_statement_extractor`."""
    model = AnthropicModel(
        MORTGAGE_AGENT_MODEL,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    )
    return Agent(
        model,
        output_type=ExtractedMortgage,
        system_prompt=SYSTEM_PROMPT,
    )
