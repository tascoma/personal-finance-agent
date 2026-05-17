"""Orchestrator agent — routes a batch of documents to the right sub-agent.

Given a digest (filename, file extension, and a small content peek) for each
pending document in a period, plus the user's chart of accounts, returns a
structured plan: the resolved `document_type` to use during extraction, the
matched `source_account_code` if one can be identified from the content, and
whether the classifier should run for that document afterward.

The orchestrator only decides delegation; the service layer in
`app.services.orchestrate` actually invokes the existing extractor / classifier
agents based on the returned plan.
"""

import uuid
from typing import Literal

from pydantic import BaseModel

from app.agents._base import build_agent, run_agent

ResolvedType = Literal[
    "paystub",
    "bank_statement",
    "credit_card",
    "investment",
    "mortgage_statement",
    "opening_balances",
]


SYSTEM_PROMPT = (
    "You are the orchestrator for a personal-finance bookkeeping pipeline. "
    "You are given the user's chart of accounts plus a batch of uploaded "
    "documents (filename, file extension, and a short text peek of the "
    "content). For every document, return:\n"
    "  - the correct `resolved_type` to use for extraction, and\n"
    "  - the matching `resolved_source_account_code` from the chart of "
    "accounts, or null when no confident match exists.\n\n"
    "Valid `resolved_type` values and how to recognize them:\n"
    "  - paystub: pay-period earnings/deductions, gross pay, net pay, employer name.\n"
    "  - bank_statement: posted deposits and withdrawals on a checking/savings account.\n"
    "  - credit_card: posted charges and payments on a credit-card account.\n"
    "  - investment: brokerage/retirement transactions (buys, sells, dividends).\n"
    "  - mortgage_statement: a mortgage payment breakdown (principal, interest, escrow, taxes, insurance).\n"
    "  - opening_balances: a spreadsheet of opening account balances (columns include account_code and balance).\n\n"
    "Source-account matching rules:\n"
    "  - For `bank_statement` and `credit_card`: the source account is the "
    "account the statement is about (the one whose transactions are listed). "
    "Match on the institution / product name in the content (e.g., 'Chase "
    "Sapphire ending 1234' → the account named 'Chase Sapphire Reserve'), or "
    "on a last-4 of the account number when present.\n"
    "  - For `paystub`: the source account is the checking/savings account "
    "named as the net-pay deposit destination on the stub. If no deposit "
    "account is identifiable, return null.\n"
    "  - For `investment` and `mortgage_statement`: match the brokerage / "
    "loan account named in the document.\n"
    "  - For `opening_balances`: the source account is not applicable — "
    "return null.\n"
    "  - When in doubt, return null. Do not guess.\n\n"
    "Other rules:\n"
    "  1. Never return `manual` as a `resolved_type` — pick the closest real document type from the content.\n"
    "  2. Set `run_classifier=true` ONLY for `bank_statement` and `credit_card`. Set it to `false` for every other type.\n"
    "  3. Return exactly one DocumentPlan per input document, preserving the input `document_id`.\n"
    "  4. Keep `type_reason` and `source_account_reason` to one short sentence each."
)


class AccountChoice(BaseModel):
    account_code: int
    account_name: str
    account_type: str
    sub_category: str | None = None


class DocumentDigest(BaseModel):
    document_id: uuid.UUID
    file_name: str
    file_extension: str
    content_peek: str


class DocumentPlan(BaseModel):
    document_id: uuid.UUID
    resolved_type: ResolvedType
    type_reason: str
    resolved_source_account_code: int | None = None
    source_account_reason: str | None = None
    run_classifier: bool


class OrchestrationPlan(BaseModel):
    steps: list[DocumentPlan]


def _format_accounts(accounts: list[AccountChoice]) -> str:
    if not accounts:
        return "(no accounts configured)"
    lines = []
    for a in accounts:
        sub = f" · {a.sub_category}" if a.sub_category else ""
        lines.append(f"  - {a.account_code}: {a.account_name} ({a.account_type}{sub})")
    return "\n".join(lines)


def _format_digests(
    digests: list[DocumentDigest], accounts: list[AccountChoice]
) -> str:
    blocks = [
        "Chart of accounts (use these account_code values for resolved_source_account_code):\n"
        + _format_accounts(accounts)
    ]
    for d in digests:
        blocks.append(
            f"document_id: {d.document_id}\n"
            f"file_name: {d.file_name}\n"
            f"file_extension: {d.file_extension}\n"
            f"content_peek:\n{d.content_peek}"
        )
    return "\n\n---\n\n".join(blocks)


agent = build_agent(OrchestrationPlan, SYSTEM_PROMPT)


async def run_orchestrator(
    digests: list[DocumentDigest], accounts: list[AccountChoice]
) -> OrchestrationPlan:
    prompt = _format_digests(digests, accounts)
    return await run_agent(agent, "orchestrator", prompt)
