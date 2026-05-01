# Personal Finance Agent

A personal double-entry accounting system with an AI-powered document and transaction intelligence backend. Upload bank statements, paystubs, and mortgage documents; let AI agents extract and classify transactions; then follow a structured monthly close workflow to maintain an accurate general ledger.

## Stack

- **FastAPI** — async web framework with dependency injection
- **Pydantic AI** — structured LLM agent framework (Claude Sonnet 4.6)
- **Pydantic v2** — request/response schemas and settings via `BaseSettings`
- **SQLAlchemy 2.0** — async ORM (SQLite by default, PostgreSQL-compatible)
- **Jinja2** — server-side HTML templating
- **uv** — dependency and virtual environment management

## Features

- Upload and AI-parse bank/credit card statements, paystubs, and mortgage statements (PDF, CSV, XLSX)
- AI transaction classifier assigns account codes with confidence scores
- Double-entry journal with debit/credit constraints enforced at the DB level
- Period-based monthly close workflow: `open → pending_review → pending_close → closed`
- Reconciliation engine comparing computed book balances to stated bank balances
- AI reconciliation analyzer surfaces likely gap causes and remediation steps
- Automatic closing entries to zero income/expense accounts and roll equity
- Financial statements: Balance Sheet, Income Statement, Cash Flow Statement
- Dashboard with net worth trends and expense breakdowns

## Getting started

### 1. Install dependencies

```bash
uv venv
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

```env
APP_ENV=development
SECRET_KEY=changeme
DATABASE_URL=sqlite+aiosqlite:///./app.db
ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Run the dev server

```bash
python3 -m app.main
```

Or directly with uvicorn:

```bash
uv run uvicorn app.main:app --reload
```

The app starts at `http://127.0.0.1:8000`.

## Monthly close workflow

Each accounting period follows a linear status progression. Here's the full workflow from period creation to close.

### 1. Open a period

Create a new accounting period for the month. Each calendar month can have at most one period.

### 2. Upload documents

Upload supporting documents — bank/credit card statements, paystubs, mortgage statements. The system accepts PDF, CSV, and XLSX formats. AI agents parse each document and stage extracted transactions for review.

### 3. Classify transactions

Set the source account (e.g., the checking account) for each document. Run the AI classifier to assign suggested account codes and confidence scores to unclassified transactions. Low-confidence suggestions (<0.7) are flagged for manual review. Approve or reject each transaction.

### 4. Post to journal

Advance the period to `pending_close`. Review approved transactions and optionally add manual journal entries for adjustments. Post all approved transactions to the general ledger as double-entry journal entries.

### 5. Reconcile

Enter stated ending balances from bank statements. Run the reconciliation engine to compute the gap between book and stated balances. Optionally invoke the AI reconciliation analyzer to identify likely causes (missing transactions, duplicates, timing differences). Post adjusting entries where needed.

### 6. Close

Post closing entries to zero out income and expense accounts and roll net income into equity. Close the period. Closed periods can be reopened for corrections.

## AI agents

| Agent | Purpose |
|---|---|
| **Statement Extractor** | Parses bank/credit card/investment statement PDFs; extracts date, description, and signed amount per transaction |
| **Paystub Extractor** | Extracts payroll line items (earnings, deductions, taxes, net pay) from paystub PDFs |
| **Mortgage Extractor** | Extracts principal, interest, escrow, property tax, and insurance amounts from mortgage statement PDFs |
| **Transaction Classifier** | Assigns account codes with confidence scores; considers source account type for sign interpretation |
| **Reconciliation Analyzer** | Identifies likely causes of reconciliation gaps and suggests concrete remediation steps |

## Project structure

```
personal-finance-agent/
├── app/
│   ├── main.py              # FastAPI app instance, router includes, lifespan
│   ├── core/
│   │   ├── config.py        # Pydantic BaseSettings (env-driven)
│   │   └── logging.py       # Logging configuration
│   ├── databases/           # SQLAlchemy engine and session factory
│   ├── dependencies/        # Shared Depends() factories
│   ├── routes/              # APIRouter modules (dashboard, accounts, ledger, periods)
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── agents/              # Pydantic AI agent definitions (classifier, statement, paystub, mortgage, reconciliation)
│   ├── services/            # Business logic layer
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── tests/
├── logs/
└── uploads/
```

## Domain concepts

**Account** — A chart-of-accounts entry with a numeric code, type (Asset / Liability / Equity / Income / Expense), normal balance (debit or credit), and optional paystub label mapping.

**Period** — A calendar month with a linear status lifecycle. Only one period per month is allowed.

**Document** — An uploaded file linked to a period with a type (statement, paystub, mortgage, manual) and a source account representing where the money flows from.

**Raw Transaction** — An extracted transaction staged for review. Carries a suggested account code, classifier confidence score, and a dedup hash for duplicate detection. Status flows: `staged → approved → posted` (or `rejected`).

**Journal Entry / Journal Line** — A double-entry journal entry header with one or more debit/credit lines. The DB enforces that exactly one of `debit_amount` or `credit_amount` is non-zero per line.

**Reconciliation** — A per-account, per-period record comparing the computed book balance (from journal entries) against the user-entered stated balance. Gap = stated − computed. Status: `pending` (gap exists), `reconciled` (gap = 0), or `adjusted` (adjusting entry posted).
