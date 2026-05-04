import logging
from datetime import date

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

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


agent = Agent(
    AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key),
    ),
    output_type=ExtractedMortgage,
    system_prompt=SYSTEM_PROMPT,
)


async def run_mortgage_extractor(text: str) -> ExtractedMortgage:
    logger.debug("Running mortgage extractor (text length=%d)", len(text))
    try:
        result = await agent.run(text)
    except Exception:
        logger.exception("Mortgage extractor failed")
        raise
    logger.debug("Mortgage extractor succeeded: payment_date=%s", result.output.payment_date)
    return result.output
