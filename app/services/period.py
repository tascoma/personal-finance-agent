"""Period service — month-based accounting periods.

Periods are the root workflow entity. Each period represents one calendar month
and progresses through a linear status lifecycle:

    open → pending_review → pending_close → closed

A closed period can also be reopened (closed → open), resetting closed_at.

Business rules:
- period_start is the first day of the month; period_end is the last day.
- Only one period may exist per month (enforced by unique index on period_start).
- Forward transitions are one step at a time along the lifecycle.
- A period can only be deleted while it is still `open`.
"""

import calendar
import logging
import uuid
from datetime import date, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.period import Period

logger = logging.getLogger(__name__)

_STATUS_ORDER: tuple[str, ...] = ("open", "pending_review", "pending_close", "closed")


def next_status(current: str) -> str | None:
    """Return the next status in the lifecycle, or None if already at the end."""
    try:
        idx = _STATUS_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(_STATUS_ORDER):
        return None
    return _STATUS_ORDER[idx + 1]


class PeriodError(Exception):
    """Raised for invalid period operations (bad input, conflicts, illegal transitions)."""


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first-day, last-day) for the given calendar month."""
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    last = date(year, month, last_day)
    return first, last


async def create_period(db: AsyncSession, year: int, month: int) -> Period:
    start, end = month_bounds(year, month)
    existing = await db.scalar(select(Period).where(Period.period_start == start))
    if existing is not None:
        raise PeriodError(f"Period for {year}-{month:02d} already exists")
    period = Period(period_start=start, period_end=end, status="open")
    db.add(period)
    await db.commit()
    await db.refresh(period)
    logger.info("Created period %s (%s → %s)", period.period_id, start, end)
    return period


async def list_periods(db: AsyncSession) -> Sequence[Period]:
    result = await db.scalars(select(Period).order_by(Period.period_start.desc()))
    return result.all()


async def get_period(db: AsyncSession, period_id: uuid.UUID) -> Period | None:
    return await db.get(Period, period_id)


async def get_current_open_period(db: AsyncSession) -> Period | None:
    """Most recent period in `open` status — the one the user is actively working on."""
    return await db.scalar(
        select(Period)
        .where(Period.status == "open")
        .order_by(Period.period_start.desc())
        .limit(1)
    )


async def update_status(
    db: AsyncSession, period_id: uuid.UUID, new_status: str
) -> Period:
    period = await db.get(Period, period_id)
    if period is None:
        raise PeriodError("Period not found")

    try:
        current_idx = _STATUS_ORDER.index(period.status)
        target_idx = _STATUS_ORDER.index(new_status)
    except ValueError as exc:
        raise PeriodError(f"Unknown status: {exc}") from exc

    # Forward-only transitions, one step at a time. This keeps the close workflow
    # honest — you can't skip from 'open' straight to 'closed' and bypass review.
    if target_idx != current_idx + 1:
        raise PeriodError(
            f"Illegal transition {period.status} → {new_status}"
        )

    period.status = new_status
    if new_status == "closed":
        period.closed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(period)
    logger.info("Period %s → %s", period.period_id, new_status)
    return period


async def reopen_period(db: AsyncSession, period_id: uuid.UUID) -> Period:
    period = await db.get(Period, period_id)
    if period is None:
        raise PeriodError("Period not found")
    if period.status != "closed":
        raise PeriodError(f"Only closed periods can be reopened (current: {period.status})")
    period.status = "open"
    period.closed_at = None
    await db.commit()
    await db.refresh(period)
    logger.info("Reopened period %s", period.period_id)
    return period


async def delete_period(db: AsyncSession, period_id: uuid.UUID) -> None:
    period = await db.get(Period, period_id)
    if period is None:
        raise PeriodError("Period not found")
    if period.status != "open":
        raise PeriodError("Only periods in 'open' status can be deleted")
    await db.delete(period)
    await db.commit()
    logger.info("Deleted period %s", period_id)
