"""Deterministic CSV/XLSX → ExtractedTxn mapping.

Targets two real file shapes the user actually exports:
  - Bank OZK CSV: ``Date, Description, ChkRef, Amount, Balance``
    Amount is a string like ``"$2,569.00 "`` or ``"($25.00)"`` (parens = negative).
  - EJ Mastercard XLSX: ``Date, Transaction, Name, Memo, Amount``
    Amount is already a numeric Excel value (negative = charge).

When a third format shows up, extend the alias lists below — don't build a
generic schema-detection framework.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agents.statement import ExtractedTxn
from app.services.file_readers import ParseError

DATE_ALIASES: tuple[str, ...] = ("date", "transaction date", "posted date", "post date")
DESC_ALIASES: tuple[str, ...] = ("description", "name", "memo", "payee", "merchant")
AMOUNT_ALIASES: tuple[str, ...] = ("amount", "transaction amount")

DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%-m/%-d/%y",
    "%-m/%-d/%Y",
    "%m-%d-%Y",
)


def _norm(s: Any) -> str:
    return (str(s) if s is not None else "").strip().lower()


def _pick(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    """Return the first header whose lowercased form matches one of the aliases."""
    lookup = {_norm(h): h for h in headers}
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    return None


def _coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        raise ParseError("Empty date value")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Unrecognized date format: {text!r}")


def _coerce_amount(value: Any) -> Decimal:
    """Parse an amount string or Decimal. Handles ``$1,234.56`` and ``(12.34)`` (= -12.34)."""
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        raise ParseError("Empty amount")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = re.sub(r"[\$,\s]", "", text)
    if not text:
        raise ParseError("Empty amount after stripping symbols")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(f"Unrecognized amount format: {value!r}") from exc
    return -amount if negative else amount


def csv_to_transactions(rows: list[dict[str, str]]) -> list[ExtractedTxn]:
    if not rows:
        raise ParseError("No CSV rows to map")
    headers = list(rows[0].keys())
    return _rows_to_transactions(headers, [list(r.values()) for r in rows], headers)


def xlsx_to_transactions(rows: list[list[Any]]) -> list[ExtractedTxn]:
    if not rows:
        raise ParseError("No XLSX rows to map")
    headers_raw = rows[0]
    headers = [str(h) if h is not None else "" for h in headers_raw]
    return _rows_to_transactions(headers, rows[1:], headers)


def _rows_to_transactions(
    headers: list[str], data_rows: list[list[Any]], header_lookup: list[str]
) -> list[ExtractedTxn]:
    date_col = _pick(header_lookup, DATE_ALIASES)
    desc_col = _pick(header_lookup, DESC_ALIASES)
    amount_col = _pick(header_lookup, AMOUNT_ALIASES)
    if not date_col or not desc_col or not amount_col:
        raise ParseError(
            f"Missing required columns. Headers: {headers}. "
            f"Need date={date_col!r}, description={desc_col!r}, amount={amount_col!r}."
        )

    date_idx = headers.index(date_col)
    desc_idx = headers.index(desc_col)
    amount_idx = headers.index(amount_col)

    results: list[ExtractedTxn] = []
    for row in data_rows:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        try:
            txn_date = _coerce_date(row[date_idx])
            description = str(row[desc_idx] or "").strip()
            amount = _coerce_amount(row[amount_idx])
        except (IndexError, ParseError):
            # Skip rows we can't decode — totals/footers/blank lines.
            continue
        if not description:
            continue
        results.append(
            ExtractedTxn(txn_date=txn_date, description=description, amount=amount)
        )

    if not results:
        raise ParseError("Mapper produced zero transactions")
    return results
