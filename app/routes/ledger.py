"""Ledger view — read-only listing of all journal entries grouped by period."""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.period import Period
from app.services import statements as statements_service

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/ledger", response_class=HTMLResponse)
async def ledger(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    periods_result = await db.scalars(
        select(Period).order_by(Period.period_start.desc())
    )
    periods = periods_result.all()

    entries_result = await db.scalars(
        select(JournalEntry).order_by(
            JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()
        )
    )
    entries = entries_result.all()

    entries_by_period: dict[uuid.UUID, list[JournalEntry]] = {p.period_id: [] for p in periods}
    for entry in entries:
        entries_by_period.setdefault(entry.period_id, []).append(entry)

    lines_by_entry: dict[uuid.UUID, list[JournalLine]] = {e.entry_id: [] for e in entries}
    if entries:
        lines_result = await db.scalars(
            select(JournalLine).where(
                JournalLine.entry_id.in_([e.entry_id for e in entries])
            )
        )
        for line in lines_result.all():
            lines_by_entry.setdefault(line.entry_id, []).append(line)

    accounts_result = await db.scalars(select(Account).order_by(Account.account_code))
    accounts_by_code = {a.account_code: a for a in accounts_result.all()}

    return templates.TemplateResponse(
        request,
        "ledger.html",
        {
            "periods": periods,
            "entries_by_period": entries_by_period,
            "lines_by_entry": lines_by_entry,
            "accounts_by_code": accounts_by_code,
        },
    )


@router.get("/ledger/statements", response_class=HTMLResponse)
async def statements(
    request: Request,
    period_id: str | None = Query(default=None),
    tab: str = Query(default="balance_sheet"),
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    periods = await statements_service.list_periods_desc(db)

    selected_period: Period | None = None
    period_ids: list[uuid.UUID] | None = None
    range_label = "All periods"

    if period_id:
        try:
            pid = uuid.UUID(period_id)
        except ValueError:
            pid = None
        if pid is not None:
            selected_period = next((p for p in periods if p.period_id == pid), None)
        if selected_period is not None:
            period_ids = [selected_period.period_id]
            range_label = selected_period.period_start.strftime("%B %Y")

    if tab not in {"balance_sheet", "income_statement", "cashflows"}:
        tab = "balance_sheet"

    # Cash flow statement uses the indirect method and must show one period at a time.
    if tab == "cashflows" and selected_period is None and periods:
        selected_period = periods[0]  # periods sorted desc → most recent first
        period_ids = [selected_period.period_id]
        range_label = selected_period.period_start.strftime("%B %Y")

    logger.debug(
        "Computing statements: tab=%s period_ids=%s",
        tab,
        [str(p) for p in period_ids] if period_ids else "all",
    )
    balance_sheet_pivot = await statements_service.compute_balance_sheet_pivot(db)
    income_statement = await statements_service.compute_income_statement(
        db, period_ids, range_label=range_label
    )
    cashflow = await statements_service.compute_cashflow(
        db, period_ids, range_label=range_label
    )

    return templates.TemplateResponse(
        request,
        "statements.html",
        {
            "periods": periods,
            "selected_period": selected_period,
            "active_tab": tab,
            "balance_sheet_pivot": balance_sheet_pivot,
            "income_statement": income_statement,
            "cashflow": cashflow,
        },
    )
