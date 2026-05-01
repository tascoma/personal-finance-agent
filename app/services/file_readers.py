"""Pure-Python file readers for documents in the Parse phase.

These functions turn a file on disk into structured Python data. They never
call the LLM and never touch the database. The orchestrator in
`app.services.parse` decides whether the result goes to a deterministic mapper
or to an extractor agent.
"""

import csv as _csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber


class ParseError(Exception):
    """Raised when a file is corrupt, empty, or in an unrecognized shape."""


def extract_pdf_text(path: Path) -> str:
    """Return all page text joined by blank lines. Empty PDFs raise ParseError."""
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise ParseError(f"Could not open PDF {path}: {exc}") from exc

    text = "\n\n".join(pages).strip()
    if not text:
        raise ParseError(f"PDF {path} contains no extractable text")
    return text


def extract_xlsx_rows(path: Path) -> list[list[Any]]:
    """Return rows from the first sheet, skipping fully-empty rows."""
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception as exc:
        raise ParseError(f"Could not open XLSX {path}: {exc}") from exc

    try:
        sheet = wb.active
        if sheet is None:
            raise ParseError(f"XLSX {path} has no active sheet")
        rows: list[list[Any]] = []
        for raw in sheet.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() != "" for cell in raw):
                rows.append(list(raw))
    finally:
        wb.close()

    if not rows:
        raise ParseError(f"XLSX {path} is empty")
    return rows


def extract_csv_rows(path: Path) -> list[dict[str, str]]:
    """Return rows from a CSV file as a list of dicts keyed by header."""
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = _csv.DictReader(fh)
            if not reader.fieldnames:
                raise ParseError(f"CSV {path} has no header row")
            # DictReader puts extra trailing columns under the None key as a list;
            # drop those — we only want named columns with scalar string values.
            rows = [
                {k: (v or "").strip() for k, v in row.items()
                 if k is not None and isinstance(v, str)}
                for row in reader
            ]
    except UnicodeDecodeError as exc:
        raise ParseError(f"CSV {path} is not valid UTF-8: {exc}") from exc
    except _csv.Error as exc:
        raise ParseError(f"CSV {path} is malformed: {exc}") from exc

    if not rows:
        raise ParseError(f"CSV {path} contains no data rows")
    return rows


def read_opening_balances_xlsx(path: Path) -> list[tuple[int, Decimal]]:
    """Return (account_code, balance) pairs from an opening-balances workbook.

    Format: first sheet, header row in row 1 with columns named ``account_code``
    and ``balance`` (case-insensitive, leading/trailing whitespace tolerated).
    Extra columns are ignored; rows with a blank account_code are skipped.
    Sign convention is the caller's job — this reader stays purely structural.
    """
    rows = extract_xlsx_rows(path)
    header = [str(c or "").strip().lower() for c in rows[0]]
    try:
        code_idx = header.index("account_code")
        bal_idx = header.index("balance")
    except ValueError as exc:
        raise ParseError(
            f"Opening-balances XLSX {path} must have columns "
            "'account_code' and 'balance' in row 1"
        ) from exc

    out: list[tuple[int, Decimal]] = []
    for row_num, row in enumerate(rows[1:], start=2):
        if code_idx >= len(row) or row[code_idx] in (None, ""):
            continue
        try:
            code = int(str(row[code_idx]).strip())
        except (TypeError, ValueError) as exc:
            raise ParseError(
                f"Row {row_num}: account_code {row[code_idx]!r} is not an integer"
            ) from exc
        raw_amount = row[bal_idx] if bal_idx < len(row) else None
        if raw_amount in (None, ""):
            continue
        try:
            amount = Decimal(str(raw_amount).replace(",", "").replace("$", "").strip())
        except InvalidOperation as exc:
            raise ParseError(
                f"Row {row_num} (account {code}): balance {raw_amount!r} is not a number"
            ) from exc
        out.append((code, amount))

    if not out:
        raise ParseError(f"Opening-balances XLSX {path} has no balance rows")
    return out
