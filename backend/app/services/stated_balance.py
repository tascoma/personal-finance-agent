"""Stated balance service — month-end closing balances per account.

Stated balances are user-entered targets used during the Close phase to
reconcile against the system-computed balance. Non-memo Asset/Liability
accounts carry a stated balance for reconciliation; memo accounts (e.g.
unvested RSUs) also carry a stated balance as a point-in-time snapshot
for off-balance-sheet disclosure, but are excluded from reconciliation.
"""

import logging
import uuid
from decimal import Decimal
from typing import Sequence

from sqlalchemy import and_, or_, select
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

    row = await db.scalar(
        select(StatedBalance).where(
            StatedBalance.period_id == period_id,
            StatedBalance.account_code == account_code,
        )
    )
    if row is None:
        row = StatedBalance(
            period_id=period_id,
            account_code=account_code,
            stated_balance=stated_balance,
        )
        db.add(row)
    else:
        row.stated_balance = stated_balance
    await db.commit()
    await db.refresh(row)
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
    """Accounts that carry a month-end stated balance.

    Non-memo Asset/Liability accounts (for reconciliation) plus memo accounts
    such as unvested RSUs (point-in-time snapshot for off-BS disclosure).
    """
    result = await db.scalars(
        select(Account)
        .where(
            or_(
                and_(
                    Account.account_type.in_(("Asset", "Liability")),
                    Account.is_memo == False,  # noqa: E712 — SQL boolean
                ),
                Account.is_memo == True,  # noqa: E712
            ),
            Account.is_active == True,  # noqa: E712
        )
        .order_by(Account.account_code)
    )
    return result.all()
