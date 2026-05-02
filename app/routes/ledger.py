import logging
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.period import Period
from app.schemas.account import AccountRead
from app.schemas.api_responses import JournalEntryWithLines, LedgerResponse
from app.schemas.journal import JournalEntryRead, JournalLineRead
from app.schemas.period import PeriodRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ledger"])


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger(
    db: AsyncSession = Depends(get_db_session),
) -> LedgerResponse:
    periods_result = await db.scalars(select(Period).order_by(Period.period_start.desc()))
    periods = list(periods_result.all())

    entries_result = await db.scalars(
        select(JournalEntry).order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    )
    entries = list(entries_result.all())

    lines_result = await db.scalars(select(JournalLine))
    lines_by_entry: dict = defaultdict(list)
    for line in lines_result.all():
        lines_by_entry[line.entry_id].append(line)

    accounts_result = await db.scalars(select(Account).where(Account.is_active.is_(True)))
    accounts = {a.account_code: AccountRead.model_validate(a) for a in accounts_result.all()}

    entries_by_period: dict[str, list[JournalEntryWithLines]] = defaultdict(list)
    for entry in entries:
        entry_lines = [JournalLineRead.model_validate(ln) for ln in lines_by_entry.get(entry.entry_id, [])]
        base = JournalEntryRead.model_validate(entry).model_dump()
        entries_by_period[str(entry.period_id)].append(
            JournalEntryWithLines(**base, lines=entry_lines)
        )

    return LedgerResponse(
        periods=[PeriodRead.model_validate(p) for p in periods],
        entries_by_period=dict(entries_by_period),
        accounts_by_code={code: acct for code, acct in accounts.items()},
    )
