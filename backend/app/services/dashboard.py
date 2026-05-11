"""Dashboard metrics — all data computed in two queries (lines + recent entries)."""

import uuid
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
class ExpenseCategorySeriesPoint:
    period_label: str
    category: str
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
    investing_cashflow: Decimal
    salary_income: Decimal
    retirement_contributions: Decimal
    compensation_income: Decimal
    lifestyle_expenses: Decimal
    period_bars: list[PeriodBar]
    net_worth_series: list[NetWorthPoint]
    top_expense_categories: list[ExpenseCategory]
    expense_category_series: list[ExpenseCategorySeriesPoint]
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


# Dining Out + Alcohol are treated as discretionary alongside the "Lifestyle"
# sub_category (Travel, Entertainment, Hobbies, Electronics).
_LIFESTYLE_EXTRA_CODES = {520102, 520103}


def _is_lifestyle(acct: Account) -> bool:
    return acct.sub_category == "Lifestyle" or acct.account_code in _LIFESTYLE_EXTRA_CODES


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


async def compute_dashboard(
    db: AsyncSession,
    year: Optional[int] = None,
    period_id: Optional[uuid.UUID] = None,
) -> DashboardData:
    accounts_result = await db.scalars(select(Account))
    accounts: dict[int, Account] = {a.account_code: a for a in accounts_result.all()}

    periods_result = await db.scalars(select(Period).order_by(Period.period_start.asc()))
    all_periods = list(periods_result.all())

    if period_id is not None:
        periods = [p for p in all_periods if p.period_id == period_id]
    elif year is not None:
        periods = [p for p in all_periods if p.period_start.year == year]
    else:
        periods = all_periods

    # Only closed periods contribute to any metric or chart.
    all_closed_periods = [p for p in all_periods if p.status == "closed"]
    all_closed_ids = {p.period_id for p in all_closed_periods}

    closed_filter_periods = [p for p in periods if p.status == "closed"]
    filter_closed_ids = {p.period_id for p in closed_filter_periods}

    # Balance-sheet figures are cumulative — use all closed periods up to and
    # including the last closed period in the filter selection so that
    # total_assets / net_worth reflect the actual balance, not just the period's change.
    if closed_filter_periods:
        max_filter_start = max(p.period_start for p in closed_filter_periods)
        bs_period_ids = {p.period_id for p in all_closed_periods if p.period_start <= max_filter_start}
    else:
        bs_period_ids = all_closed_ids

    rows = await db.execute(
        select(JournalLine, JournalEntry.period_id, JournalEntry.entry_id, JournalEntry.is_closing)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.entry_id)
    )
    all_rows = rows.all()

    # lines_bs_all     — all closed periods up to last filtered period (balance-sheet KPI totals)
    # lines_bs_by_pid  — all closed periods by period (net-worth series running total)
    # lines_operating  — filtered closed periods, no closing entries (income/expense flow figures)
    lines_bs_all: list[JournalLine] = []
    lines_bs_by_pid: dict = defaultdict(list)
    lines_operating: list[JournalLine] = []
    lines_operating_by_period: dict = defaultdict(list)
    lines_operating_by_entry: dict = defaultdict(list)
    for line, pid, entry_id, is_closing in all_rows:
        if pid in all_closed_ids:
            lines_bs_by_pid[pid].append(line)
        if pid in bs_period_ids:
            lines_bs_all.append(line)
        if pid in filter_closed_ids and not is_closing:
            lines_operating.append(line)
            lines_operating_by_period[pid].append(line)
            lines_operating_by_entry[entry_id].append(line)

    # Income/Expense must exclude closing entries — closing entries zero out those
    # accounts by reversing them into equity, so including them cancels everything to zero.
    total_income = _sum_by_type(lines_operating, accounts, "Income")
    total_expenses = _sum_by_type(lines_operating, accounts, "Expense")
    net_income = total_income - total_expenses
    total_assets = _sum_by_type(lines_bs_all, accounts, "Asset")
    total_liabilities = _sum_by_type(lines_bs_all, accounts, "Liability")
    net_worth = total_assets - total_liabilities

    cash_codes = {code for code, a in accounts.items() if a.account_type == "Asset" and "cash" in a.sub_category.lower()}
    wc_codes = {code for code, a in accounts.items() if a.account_type == "Liability" and a.sub_category == "Credit Cards"}
    investing_bucket: dict[int, Decimal] = defaultdict(lambda: _ZERO)
    for entry_lines in lines_operating_by_entry.values():
        if not any(ln.account_code in cash_codes for ln in entry_lines):
            continue
        # Opening balance entries credit equity alongside asset debits — exclude them
        # so their starting balances don't distort investing cashflow.
        if any(accounts.get(ln.account_code) and accounts[ln.account_code].account_type == "Equity" for ln in entry_lines):
            continue
        for ln in entry_lines:
            if ln.account_code in cash_codes or ln.account_code in wc_codes:
                continue
            acct = accounts.get(ln.account_code)
            if acct is None or acct.account_type in ("Income", "Expense"):
                continue
            if acct.account_type == "Asset":
                investing_bucket[ln.account_code] += ln.credit_amount - ln.debit_amount
    investing_cashflow = sum(investing_bucket.values(), _ZERO)

    salary_income = sum(
        (ln.credit_amount - ln.debit_amount for ln in lines_operating if ln.account_code == 400101),
        _ZERO,
    )

    # Retirement contributions: only count changes from cash-touching entries so
    # investment value adjustments (which post against Income/Equity, not cash) are excluded.
    _retirement_codes = {111101, 111102, 111103}
    retirement_contributions = _ZERO
    for entry_lines in lines_operating_by_entry.values():
        if not any(ln.account_code in cash_codes for ln in entry_lines):
            continue
        if any(accounts.get(ln.account_code) and accounts[ln.account_code].account_type == "Equity" for ln in entry_lines):
            continue
        for ln in entry_lines:
            if ln.account_code in _retirement_codes:
                retirement_contributions += ln.debit_amount - ln.credit_amount
    _compensation_codes = {400101, 400102}
    compensation_income = sum(
        (ln.credit_amount - ln.debit_amount for ln in lines_operating if ln.account_code in _compensation_codes),
        _ZERO,
    )

    lifestyle_expenses = _ZERO
    for ln in lines_operating:
        acct = accounts.get(ln.account_code)
        if acct is None or acct.is_memo or acct.account_type != "Expense":
            continue
        if _is_lifestyle(acct):
            lifestyle_expenses += ln.debit_amount - ln.credit_amount

    # Walk ALL closed periods in chronological order so the running balance-sheet
    # total is always correct. Only emit chart points for periods in the filter.
    period_bars: list[PeriodBar] = []
    running_assets = _ZERO
    running_liabilities = _ZERO
    net_worth_series: list[NetWorthPoint] = []
    expense_category_series: list[ExpenseCategorySeriesPoint] = []

    for p in all_closed_periods:
        p_bs_lines = lines_bs_by_pid.get(p.period_id, [])
        running_assets += _sum_by_type(p_bs_lines, accounts, "Asset")
        running_liabilities += _sum_by_type(p_bs_lines, accounts, "Liability")

        if p.period_id not in filter_closed_ids:
            continue

        p_op_lines = lines_operating_by_period.get(p.period_id, [])
        p_income = _sum_by_type(p_op_lines, accounts, "Income")
        p_expenses = _sum_by_type(p_op_lines, accounts, "Expense")
        label = p.period_start.strftime("%b %Y")
        period_bars.append(PeriodBar(
            label=label,
            income=float(p_income),
            expenses=float(p_expenses),
            net=float(p_income - p_expenses),
        ))
        net_worth_series.append(NetWorthPoint(
            label=label,
            net_worth=float(running_assets - running_liabilities),
        ))

        per_cat: dict[str, Decimal] = defaultdict(lambda: _ZERO)
        for ln in p_op_lines:
            acct = accounts.get(ln.account_code)
            if acct is None or acct.account_type != "Expense" or acct.is_memo:
                continue
            per_cat[acct.sub_category] += ln.debit_amount - ln.credit_amount
        for cat, amt in per_cat.items():
            if amt > _ZERO:
                expense_category_series.append(ExpenseCategorySeriesPoint(
                    period_label=label,
                    category=cat,
                    amount=float(amt),
                ))

    top_expense_categories = _expense_by_subcategory(lines_operating, accounts)

    recent_result = await db.execute(
        select(JournalEntry, Period.period_start)
        .join(Period, JournalEntry.period_id == Period.period_id)
        .where(JournalEntry.period_id.in_(filter_closed_ids))
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .limit(6)
    )
    period_labels: dict = {p.period_id: p.period_start.strftime("%b %Y") for p in all_closed_periods}

    lines_by_entry: dict = defaultdict(list)
    for line, period_id, entry_id, _is_closing in all_rows:
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

    has_data = len(lines_bs_all) > 0

    return DashboardData(
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=net_income,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        investing_cashflow=investing_cashflow,
        salary_income=salary_income,
        retirement_contributions=retirement_contributions,
        compensation_income=compensation_income,
        lifestyle_expenses=lifestyle_expenses,
        period_bars=period_bars,
        net_worth_series=net_worth_series,
        top_expense_categories=top_expense_categories,
        expense_category_series=expense_category_series,
        recent_entries=recent_entries,
        period_count=len(closed_filter_periods),
        has_data=has_data,
    )
