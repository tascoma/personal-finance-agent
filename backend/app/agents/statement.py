from datetime import date

from pydantic import BaseModel

from app.agents._base import build_agent, run_agent

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


agent = build_agent(ExtractedStatement, SYSTEM_PROMPT)


async def run_statement_extractor(text: str) -> ExtractedStatement:
    return await run_agent(agent, "statement extractor", text)
