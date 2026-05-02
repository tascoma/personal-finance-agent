from collections.abc import AsyncGenerator

from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classifier import build_classifier_agent
from app.agents.mortgage import build_mortgage_extractor
from app.agents.paystub import build_paystub_extractor
from app.agents.reconciliation import build_reconciliation_agent
from app.agents.statement import build_statement_extractor
from app.core.config import settings
from app.databases import get_db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def _require_api_key() -> None:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — cannot build agent")


def get_statement_extractor() -> Agent:
    _require_api_key()
    return build_statement_extractor()


def get_paystub_extractor() -> Agent:
    _require_api_key()
    return build_paystub_extractor()


def get_mortgage_extractor() -> Agent:
    _require_api_key()
    return build_mortgage_extractor()


def get_classifier_agent() -> Agent:
    _require_api_key()
    return build_classifier_agent()


def get_reconciliation_agent() -> Agent:
    _require_api_key()
    return build_reconciliation_agent()
