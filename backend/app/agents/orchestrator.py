"""Orchestrator agent — routes a batch of documents to the right sub-agent.

Given a digest (filename, declared type, file extension, and a small content
peek) for each pending document in a period, returns a structured plan: the
resolved `document_type` to use during extraction and whether the classifier
should run for that document afterward.

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
    "You are given a batch of uploaded documents, each with a filename, a "
    "user-declared `document_type`, the file extension, and a short text "
    "peek of the content. Your job: for every document, return the correct "
    "`resolved_type` to use for extraction.\n\n"
    "Valid `resolved_type` values and how to recognize them:\n"
    "  - paystub: pay-period earnings/deductions, gross pay, net pay, employer name.\n"
    "  - bank_statement: posted deposits and withdrawals on a checking/savings account.\n"
    "  - credit_card: posted charges and payments on a credit-card account.\n"
    "  - investment: brokerage/retirement transactions (buys, sells, dividends).\n"
    "  - mortgage_statement: a mortgage payment breakdown (principal, interest, escrow, taxes, insurance).\n"
    "  - opening_balances: a spreadsheet of opening account balances (columns include account_code and balance).\n\n"
    "Rules:\n"
    "  1. The user's `declared_type` is a hint, not ground truth. Override it when the content peek clearly disagrees.\n"
    "  2. Never return `manual` as a resolved_type — pick the closest real document type from the content.\n"
    "  3. Set `run_classifier=true` ONLY for `bank_statement` and `credit_card`. Set it to `false` for every other type.\n"
    "  4. Return exactly one DocumentPlan per input document, preserving the input `document_id`.\n"
    "  5. Keep `reason` to one short sentence."
)


class DocumentDigest(BaseModel):
    document_id: uuid.UUID
    file_name: str
    declared_type: str
    file_extension: str
    content_peek: str


class DocumentPlan(BaseModel):
    document_id: uuid.UUID
    resolved_type: ResolvedType
    reason: str
    run_classifier: bool


class OrchestrationPlan(BaseModel):
    steps: list[DocumentPlan]


def _format_digests(digests: list[DocumentDigest]) -> str:
    blocks = []
    for d in digests:
        blocks.append(
            f"document_id: {d.document_id}\n"
            f"file_name: {d.file_name}\n"
            f"declared_type: {d.declared_type}\n"
            f"file_extension: {d.file_extension}\n"
            f"content_peek:\n{d.content_peek}"
        )
    return "\n\n---\n\n".join(blocks)


agent = build_agent(OrchestrationPlan, SYSTEM_PROMPT)


async def run_orchestrator(digests: list[DocumentDigest]) -> OrchestrationPlan:
    prompt = _format_digests(digests)
    return await run_agent(agent, "orchestrator", prompt)
