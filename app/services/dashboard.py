"""Dashboard metrics — all data computed in two queries (lines + recent entries)."""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.period import Period

_ZERO = Decimal("0")


@dataclass
class PeriodBar:
    label: str
    income: float
    expenses: float
    net: float


@dataclass
class NetWorthPoint:
    label: str
    net_worth: float


@dataclass
class ExpenseCategory:
    label: str
    amount: float


@dataclass
class RecentEntry:
    description: str
    entry_date: str
    source_type: str
    period_label: str
    total_debit: float


@dataclass
class DashboardData:
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    period_bars: list[PeriodBar]
    net_worth_series: list[NetWorthPoint]
    top_expense_categories: list[ExpenseCategory]
    recent_entries: list[RecentEntry]
    period_count: int
    has_data: bool


def _sum_by_type(
    lines: list[JournalLine],
    accounts: dict[int, Account],
    account_type: str,
) -> Decimal:
    total = _ZERO
    for line in lines:
        acct = accounts.get(line.account_code)
        if acct is None or acct.account_type != account_type or acct.is_memo:
            continue
        # Income accounts always contribute credit − debit regardless of normal_balance,
        # so that contra-income accounts (e.g. Capital Losses, debit-normal) correctly
        # reduce total_income rather than adding to it.
        if acct.normal_balance == "debit" and account_type != "Income":
            total += line.debit_amount - line.credit_amount
        else:
            total += line.credit_amount - line.debit_amount
    return total


def _expense_by_subcategory(
    lines: list[JournalLine],
    accounts: dict[int, Account],
) -> list[ExpenseCategory]:
    by_cat: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for line in lines:
        acct = accounts.get(line.account_code)
        if acct is None or acct.account_type != "Expense" or acct.is_memo:
            continue
        by_cat[acct.sub_category] += line.debit_amount - line.credit_amount
    return sorted(
        [ExpenseCategory(label=k, amount=float(v)) for k, v in by_cat.items() if v > _ZERO],
        key=lambda c: c.amount,
        reverse=True,
    )[:8]


async def compute_dashboard(db: AsyncSession) -> DashboardData:
    accounts_result = await db.scalars(select(Account))
    accounts: dict[int, Account] = {a.account_code: a for a in accounts_result.all()}

    periods_result = await db.scalars(select(Period).order_by(Period.period_start.asc()))
    periods = list(periods_result.all())

    rows = await db.execute(
        select(JournalLine, JournalEntry.period_id, JournalEntry.entry_id, JournalEntry.is_closing)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.entry_id)
    )
    all_rows = rows.all()

    lines_all: list[JournalLine] = []
    lines_operating: list[JournalLine] = []  # excludes closing entries
    lines_by_period: dict = defaultdict(list)
    lines_operating_by_period: dict = defaultdict(list)
    for line, period_id, entry_id, is_closing in all_rows:
        lines_all.append(line)
        lines_by_period[period_id].append(line)
        if not is_closing:
            lines_operating.append(line)
            lines_operating_by_period[period_id].append(line)

    # Income/Expense must exclude closing entries — closing entries zero out those
    # accounts by reversing them into equity, so including them cancels everything to zero.
    total_income = _sum_by_type(lines_operating, accounts, "Income")
    total_expenses = _sum_by_type(lines_operating, accounts, "Expense")
    net_income = total_income - total_expenses
    total_assets = _sum_by_type(lines_all, accounts, "Asset")
    total_liabilities = _sum_by_type(lines_all, accounts, "Liability")
    net_worth = total_assets - total_liabilities

    period_bars: list[PeriodBar] = []
    running_assets = _ZERO
    running_liabilities = _ZERO
    net_worth_series: list[NetWorthPoint] = []

    for p in periods:
        p_lines = lines_by_period.get(p.period_id, [])
        p_op_lines = lines_operating_by_period.get(p.period_id, [])
        p_income = _sum_by_type(p_op_lines, accounts, "Income")
        p_expenses = _sum_by_type(p_op_lines, accounts, "Expense")
        period_bars.append(PeriodBar(
            label=p.period_start.strftime("%b %Y"),
            income=float(p_income),
            expenses=float(p_expenses),
            net=float(p_income - p_expenses),
        ))
        running_assets += _sum_by_type(p_lines, accounts, "Asset")
        running_liabilities += _sum_by_type(p_lines, accounts, "Liability")
        net_worth_series.append(NetWorthPoint(
            label=p.period_start.strftime("%b %Y"),
            net_worth=float(running_assets - running_liabilities),
        ))

    top_expense_categories = _expense_by_subcategory(lines_operating, accounts)

    recent_result = await db.execute(
        select(JournalEntry, Period.period_start)
        .join(Period, JournalEntry.period_id == Period.period_id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .limit(6)
    )
    period_labels: dict = {p.period_id: p.period_start.strftime("%b %Y") for p in periods}

    lines_by_entry: dict = defaultdict(list)
    for line, period_id, entry_id, is_closing in all_rows:
        lines_by_entry[entry_id].append(line)

    recent_entries: list[RecentEntry] = []
    for entry, period_start in recent_result.all():
        entry_lines = lines_by_entry.get(entry.entry_id, [])
        total_debit = float(sum(ln.debit_amount for ln in entry_lines))
        recent_entries.append(RecentEntry(
            description=entry.description,
            entry_date=entry.entry_date.strftime("%Y-%m-%d"),
            source_type=entry.source_type,
            period_label=period_labels.get(entry.period_id, ""),
            total_debit=total_debit,
        ))

    has_data = len(lines_all) > 0

    return DashboardData(
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=net_income,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        period_bars=period_bars,
        net_worth_series=net_worth_series,
        top_expense_categories=top_expense_categories,
        recent_entries=recent_entries,
        period_count=len(periods),
        has_data=has_data,
    )
