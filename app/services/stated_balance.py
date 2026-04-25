"""Stated balance service — month-end closing balances per account.

Stated balances are user-entered targets used during the Close phase to
reconcile against the system-computed balance. Only Asset and Liability
accounts carry a stated balance (memo accounts excluded).
"""

import logging
import uuid
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.period import Period
from app.models.stated_balance import StatedBalance

logger = logging.getLogger(__name__)


class BalanceError(Exception):
    """Raised for invalid balance operations (closed periods, missing rows)."""


async def upsert_balance(
    db: AsyncSession,
    period_id: uuid.UUID,
    account_code: int,
    stated_balance: Decimal,
) -> StatedBalance:
    period = await db.get(Period, period_id)
    if period is None:
        raise BalanceError("Period not found")
    if period.status != "open":
        raise BalanceError("Balances can only be entered on an open period")

    stmt = sqlite_insert(StatedBalance).values(
        period_id=period_id,
        account_code=account_code,
        stated_balance=stated_balance,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["period_id", "account_code"],
        set_={"stated_balance": stmt.excluded.stated_balance},
    )
    await db.execute(stmt)
    await db.commit()

    row = await db.scalar(
        select(StatedBalance).where(
            StatedBalance.period_id == period_id,
            StatedBalance.account_code == account_code,
        )
    )
    assert row is not None  # we just upserted it
    return row


async def list_balances(
    db: AsyncSession, period_id: uuid.UUID
) -> Sequence[StatedBalance]:
    result = await db.scalars(
        select(StatedBalance)
        .where(StatedBalance.period_id == period_id)
        .order_by(StatedBalance.account_code)
    )
    return result.all()


async def list_balance_accounts(db: AsyncSession) -> Sequence[Account]:
    """Asset and Liability accounts that carry a month-end stated balance."""
    result = await db.scalars(
        select(Account)
        .where(
            Account.account_type.in_(("Asset", "Liability")),
            Account.is_memo == False,  # noqa: E712 — SQL boolean, not Python truthiness
            Account.is_active == True,  # noqa: E712
        )
        .order_by(Account.account_code)
    )
    return result.all()
