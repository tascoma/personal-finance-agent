"""Tests for the Statements page — service computations + HTTP route."""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.classifier import ClassifierOutput
from app.databases import Base
from app.dependencies import get_classifier_agent, get_db_session
from app.main import app
from app.models.account import Account
from app.models.document import Document
from app.models.raw_transaction import RawTransaction
from app.services import journal as journal_service
from app.services import period as period_service
from app.services import statements as statements_service

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session_factory():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        session.add_all([
            Account(account_code=100101, account_name="Checking", account_type="Asset",
                    sub_category="Cash", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=110101, account_name="Brokerage", account_type="Asset",
                    sub_category="Investments", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=200101, account_name="Mastercard", account_type="Liability",
                    sub_category="Credit Cards", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=300101, account_name="Owner Equity", account_type="Equity",
                    sub_category="Capital", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=400101, account_name="Salary", account_type="Income",
                    sub_category="Earned", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=520101, account_name="Groceries", account_type="Expense",
                    sub_category="Food", normal_balance="debit", is_memo=False, is_active=True),
        ])
        await session.commit()
    yield factory
    await eng.dispose()


async def _seed_period_with_entries(session_factory, year: int, month: int):
    """Create an open period and post a paystub-like + grocery entry."""
    async with session_factory() as session:
        period = await period_service.create_period(session, year, month)

    async with session_factory() as session:
        doc_pay = Document(
            period_id=period.period_id, document_type="paystub",
            file_name="pay.pdf", file_path="/tmp/pay.pdf",
            source_account_code=100101, parse_status="complete",
        )
        doc_groc = Document(
            period_id=period.period_id, document_type="bank_statement",
            file_name="bank.csv", file_path="/tmp/bank.csv",
            source_account_code=100101, parse_status="complete",
        )
        session.add_all([doc_pay, doc_groc])
        await session.commit()
        await session.refresh(doc_pay)
        await session.refresh(doc_groc)

    async with session_factory() as session:
        session.add_all([
            RawTransaction(
                document_id=doc_pay.document_id, period_id=period.period_id,
                txn_date=date(year, month, 5), description="REGULAR EARNING",
                amount=Decimal("3000.00"), suggested_account_code=400101,
                classifier_confidence=Decimal("0.99"),
                is_flagged=False, is_duplicate=False, status="approved",
            ),
            RawTransaction(
                document_id=doc_groc.document_id, period_id=period.period_id,
                txn_date=date(year, month, 12), description="WHOLE FOODS",
                amount=Decimal("-150.00"), suggested_account_code=520101,
                classifier_confidence=Decimal("0.95"),
                is_flagged=False, is_duplicate=False, status="approved",
            ),
        ])
        await session.commit()

    async with session_factory() as session:
        await journal_service.post_period(session, period.period_id)
    return period


# ── service-level tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_balance_sheet_after_paystub_and_expense(session_factory):
    period = await _seed_period_with_entries(session_factory, 2026, 1)

    async with session_factory() as session:
        bs = await statements_service.compute_balance_sheet(
            session, [period.period_id], "January 2026"
        )

    # Net pay 3000 hits checking debit; grocery -150 credits checking.
    # So Checking balance = 3000 - 150 = 2850.
    assert bs.total_assets == Decimal("2850.00")
    cash_section = next(s for s in bs.assets if s.label == "Cash")
    assert cash_section.subtotal == Decimal("2850.00")


@pytest.mark.asyncio
async def test_income_statement_net_income(session_factory):
    period = await _seed_period_with_entries(session_factory, 2026, 1)

    async with session_factory() as session:
        inc = await statements_service.compute_income_statement(
            session, [period.period_id], "January 2026"
        )

    assert inc.total_income == Decimal("3000.00")
    assert inc.total_expenses == Decimal("150.00")
    assert inc.net_income == Decimal("2850.00")


@pytest.mark.asyncio
async def test_cashflow_classifies_operating(session_factory):
    period = await _seed_period_with_entries(session_factory, 2026, 1)

    async with session_factory() as session:
        cf = await statements_service.compute_cashflow(
            session, [period.period_id], "January 2026"
        )

    # Indirect method: net income = 3000 - 150 = 2850; no non-cash items; no CC activity.
    assert cf.operating_total == Decimal("2850.00")
    assert cf.investing_total == Decimal("0")
    assert cf.financing_total == Decimal("0")
    assert cf.net_change_in_cash == Decimal("2850.00")


@pytest.mark.asyncio
async def test_aggregate_combines_periods(session_factory):
    p1 = await _seed_period_with_entries(session_factory, 2026, 1)
    p2 = await _seed_period_with_entries(session_factory, 2026, 2)

    async with session_factory() as session:
        bs_all = await statements_service.compute_balance_sheet(
            session, None, "All periods"
        )
        bs_one = await statements_service.compute_balance_sheet(
            session, [p1.period_id], "January 2026"
        )

    # Aggregate should be roughly double a single period (same seed)
    assert bs_all.total_assets == bs_one.total_assets * 2
    # Reference p2 to silence unused-fixture lint
    assert p2.period_id != p1.period_id


# ── HTTP route tests ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_db():
        async with session_factory() as session:
            yield session

    def noop_classifier():
        class _C:
            async def run(self, p):
                class _R:
                    output = ClassifierOutput(suggestions=[])
                return _R()
        return _C()

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_classifier_agent] = noop_classifier
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_statements_page_renders_empty(client):
    response = await client.get("/ledger/statements")
    assert response.status_code == 200
    assert "Balance Sheet" in response.text
    assert "Income Statement" in response.text
    assert "Cashflows" in response.text


@pytest.mark.asyncio
async def test_statements_page_renders_with_data(client, session_factory):
    await _seed_period_with_entries(session_factory, 2026, 1)
    response = await client.get("/ledger/statements")
    assert response.status_code == 200
    assert "Checking" in response.text
    assert "2850.00" in response.text  # net cash / total assets


@pytest.mark.asyncio
async def test_statements_period_filter(client, session_factory):
    period = await _seed_period_with_entries(session_factory, 2026, 1)
    response = await client.get(f"/ledger/statements?period_id={period.period_id}")
    assert response.status_code == 200
    assert "January 2026" in response.text


@pytest.mark.asyncio
async def test_statements_invalid_period_falls_back_to_aggregate(client):
    response = await client.get("/ledger/statements?period_id=not-a-uuid")
    assert response.status_code == 200
    assert "All periods" in response.text


@pytest.mark.asyncio
async def test_statements_tab_query_preserved(client):
    response = await client.get("/ledger/statements?tab=cashflows")
    assert response.status_code == 200
    # When the cashflows tab is active, its panel should not be hidden
    # while balance_sheet's panel should be.
    text = response.text
    assert 'id="tab-cashflows" style="">' in text
    assert 'id="tab-balance_sheet" style="display:none;">' in text
