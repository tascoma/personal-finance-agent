"""Diagnose EJ Roth (111101) cashflow investing for March 2026.

Pulls journal entries for the period, identifies which entries touch EJ Roth,
shows whether each entry is cash-touching (the qualifier for investing
classification), and computes what the cashflow service should report.
"""

import asyncio
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.databases import AsyncSessionLocal
from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.period import Period
from app.services import statements as svc

EJ_ROTH = 111101
_ZERO = Decimal("0")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Find March 2026 period
        period = (
            await db.scalars(
                select(Period).where(Period.period_start == date(2026, 3, 1))
            )
        ).first()
        if period is None:
            print("No period found starting 2026-03-01")
            return
        print(
            f"Period: {period.period_start}..{period.period_end} "
            f"status={period.status} id={period.period_id}"
        )

        accounts = await svc._load_accounts(db)
        lines = await svc._load_lines(db, [period.period_id], exclude_closing=True)
        cash_codes = {c for c, a in accounts.items() if svc._is_cash_account(a)}
        wc_codes = {c for c, a in accounts.items() if svc._is_working_capital_account(a)}

        # Group lines by entry
        lines_by_entry: dict = defaultdict(list)
        for ln in lines:
            lines_by_entry[ln.entry_id].append(ln)

        # Pull entry metadata for entries that touch EJ Roth
        ej_entry_ids = {
            eid for eid, lns in lines_by_entry.items()
            if any(l.account_code == EJ_ROTH for l in lns)
        }
        entries = {
            e.entry_id: e for e in (
                await db.scalars(
                    select(JournalEntry).where(JournalEntry.entry_id.in_(ej_entry_ids))
                )
            ).all()
        }

        print(f"\n{len(ej_entry_ids)} entries touch EJ Roth (111101)\n")
        print("=" * 90)

        investing_contribution = _ZERO
        skipped_no_cash = _ZERO

        for eid in sorted(ej_entry_ids, key=lambda i: (entries[i].entry_date, str(i))):
            entry = entries[eid]
            entry_lines = lines_by_entry[eid]
            has_cash = any(l.account_code in cash_codes for l in entry_lines)

            print(f"\nEntry {entry.entry_date}  is_closing={entry.is_closing}  "
                  f"src={entry.source_type}")
            print(f"  {entry.description}")
            for l in entry_lines:
                a = accounts.get(l.account_code)
                tag = ""
                if l.account_code in cash_codes:
                    tag = " [CASH]"
                elif l.account_code in wc_codes:
                    tag = " [WC]"
                elif a and a.account_type in ("Income", "Expense"):
                    tag = f" [{a.account_type}]"
                elif a:
                    tag = f" [{a.account_type}]"
                aname = a.account_name if a else "?"
                print(f"    {l.account_code} {aname:<40} "
                      f"D {l.debit_amount:>10}  C {l.credit_amount:>10}{tag}")

            # EJ Roth contribution to investing per current logic
            for l in entry_lines:
                if l.account_code != EJ_ROTH:
                    continue
                contribution = l.credit_amount - l.debit_amount
                if has_cash:
                    investing_contribution += contribution
                    print(f"  -> EJ Roth investing contribution: {contribution} "
                          f"(cash-touching entry)")
                else:
                    skipped_no_cash += contribution
                    print(f"  -> EJ Roth contribution {contribution} SKIPPED "
                          f"(no cash line in entry)")

        print("\n" + "=" * 90)
        print(f"EJ Roth net investing per current logic:  {investing_contribution}")
        print(f"EJ Roth movement in non-cash entries:     {skipped_no_cash}")
        print(f"EJ Roth total balance change in period:   "
              f"{investing_contribution + skipped_no_cash}")

        # Cross-check via raw debit-credit on the account
        ej_lines = [l for l in lines if l.account_code == EJ_ROTH]
        net_debit = sum((l.debit_amount - l.credit_amount for l in ej_lines), _ZERO)
        print(f"EJ Roth net debit (asset increase) all lines (excl closing): {net_debit}")

        # Run the service
        cf = await svc.compute_cashflow(db, [period.period_id], "March 2026")
        ej_inv = next((ln for ln in cf.investing if ln.account_code == EJ_ROTH), None)
        print(f"\nService reports EJ Roth in investing: "
              f"{ej_inv.amount if ej_inv else 'absent'}")


if __name__ == "__main__":
    asyncio.run(main())
