"""Tests for the /dashboard route.

Empty/active-period coverage exists in test_periods.py — these focus on the
aggregation paths once journal entries are present.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.databases import Base
from app.dependencies import get_current_user, get_db_session
from app.main import app
from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.period import Period
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session_factory():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def _mock_user() -> User:
        return User(user_id=uuid.uuid4(), email="test@test.com", hashed_password="", is_active=True)

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = _mock_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def closed_period_with_entries(session_factory):
    """Seed one closed period with a salary deposit and a grocery expense.

    Returns (period_id, year).
    """
    async with session_factory() as session:
        period = Period(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status="closed",
            closed_at=datetime(2026, 2, 1),
        )
        session.add(period)
        session.add_all([
            Account(account_code=100101, account_name="Checking", account_type="Asset",
                    sub_category="Cash", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=400101, account_name="Salary", account_type="Income",
                    sub_category="Earned", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=600101, account_name="Groceries", account_type="Expense",
                    sub_category="Food", normal_balance="debit", is_memo=False, is_active=True),
        ])
        await session.flush()

        salary_entry = JournalEntry(
            entry_id=uuid.uuid4(),
            period_id=period.period_id,
            entry_date=date(2026, 1, 15),
            description="Paycheck",
            source_type="manual",
        )
        grocery_entry = JournalEntry(
            entry_id=uuid.uuid4(),
            period_id=period.period_id,
            entry_date=date(2026, 1, 20),
            description="Whole Foods",
            source_type="manual",
        )
        session.add_all([salary_entry, grocery_entry])
        await session.flush()

        session.add_all([
            JournalLine(line_id=uuid.uuid4(), entry_id=salary_entry.entry_id,
                        account_code=100101, debit_amount=Decimal("3000"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=salary_entry.entry_id,
                        account_code=400101, debit_amount=Decimal("0"), credit_amount=Decimal("3000")),
            JournalLine(line_id=uuid.uuid4(), entry_id=grocery_entry.entry_id,
                        account_code=600101, debit_amount=Decimal("125"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=grocery_entry.entry_id,
                        account_code=100101, debit_amount=Decimal("0"), credit_amount=Decimal("125")),
        ])
        await session.commit()

        return period.period_id, 2026


@pytest.mark.asyncio
async def test_dashboard_empty_returns_no_data(client: AsyncClient):
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is False
    assert body["active_period"] is None
    assert body["period_bars"] == []
    assert body["net_worth_series"] == []
    assert body["top_expense_categories"] == []


@pytest.mark.asyncio
async def test_dashboard_aggregates_closed_period_entries(
    client: AsyncClient, closed_period_with_entries
):
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()

    assert body["has_data"] is True
    assert Decimal(body["total_income"]) == Decimal("3000.00")
    assert Decimal(body["total_expenses"]) == Decimal("125.00")
    assert Decimal(body["net_income"]) == Decimal("2875.00")
    assert Decimal(body["total_assets"]) == Decimal("2875.00")  # 3000 - 125 in checking
    assert Decimal(body["net_worth"]) == Decimal("2875.00")
    assert body["period_count"] == 1
    assert len(body["period_bars"]) == 1
    # top_expense_categories aggregates by sub_category, not account_name
    assert body["top_expense_categories"][0]["category"] == "Food"
    assert Decimal(body["top_expense_categories"][0]["amount"]) == Decimal("125.00")


@pytest.mark.asyncio
async def test_dashboard_year_filter(client: AsyncClient, closed_period_with_entries):
    _, year = closed_period_with_entries

    in_year = await client.get("/api/v1/dashboard", params={"year": year})
    assert Decimal(in_year.json()["total_income"]) == Decimal("3000.00")

    # Filtering to a year with no closed periods zeroes out income but
    # has_data stays true because the underlying balance-sheet lines exist.
    other = await client.get("/api/v1/dashboard", params={"year": year + 5})
    assert other.status_code == 200
    assert Decimal(other.json()["total_income"]) == Decimal("0")
    assert other.json()["period_bars"] == []


@pytest.mark.asyncio
async def test_dashboard_unknown_period_filter_returns_empty_aggregates(
    client: AsyncClient, closed_period_with_entries
):
    bogus = uuid.uuid4()
    response = await client.get("/api/v1/dashboard", params={"period_id": str(bogus)})
    assert response.status_code == 200
    assert Decimal(response.json()["total_income"]) == Decimal("0")
    assert response.json()["period_bars"] == []


@pytest_asyncio.fixture
async def closed_period_with_lifestyle(session_factory):
    """Seed one closed period with salary + bonus, groceries, travel, and dining out.

    Travel (sub_category="Lifestyle") and Dining Out (acct 520102) should both
    count as lifestyle; Groceries should not.
    """
    async with session_factory() as session:
        period = Period(
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            status="closed",
            closed_at=datetime(2026, 3, 1),
        )
        session.add(period)
        session.add_all([
            Account(account_code=100101, account_name="Checking", account_type="Asset",
                    sub_category="Cash", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=400101, account_name="Salary", account_type="Income",
                    sub_category="Earned Income", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=400102, account_name="Bonus", account_type="Income",
                    sub_category="Variable Compensation", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=520101, account_name="Groceries", account_type="Expense",
                    sub_category="Food", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=520102, account_name="Dining Out", account_type="Expense",
                    sub_category="Food", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=550101, account_name="Travel", account_type="Expense",
                    sub_category="Lifestyle", normal_balance="debit", is_memo=False, is_active=True),
        ])
        await session.flush()

        entry = JournalEntry(
            entry_id=uuid.uuid4(),
            period_id=period.period_id,
            entry_date=date(2026, 2, 15),
            description="Period activity",
            source_type="manual",
        )
        session.add(entry)
        await session.flush()

        session.add_all([
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=100101, debit_amount=Decimal("8400"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=400101, debit_amount=Decimal("0"), credit_amount=Decimal("5000")),
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=400102, debit_amount=Decimal("0"), credit_amount=Decimal("5000")),
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=520101, debit_amount=Decimal("400"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=520102, debit_amount=Decimal("200"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=entry.entry_id,
                        account_code=550101, debit_amount=Decimal("1000"), credit_amount=Decimal("0")),
        ])
        await session.commit()

        return period.period_id


@pytest.mark.asyncio
async def test_dashboard_lifestyle_and_category_series(
    client: AsyncClient, closed_period_with_lifestyle
):
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()

    # Travel (1000) + Dining Out (200); Groceries excluded.
    assert Decimal(body["lifestyle_expenses"]) == Decimal("1200.00")
    assert Decimal(body["compensation_income"]) == Decimal("10000.00")

    series = body["expense_category_series"]
    by_cat = {row["category"]: Decimal(row["amount"]) for row in series}
    # Food = Groceries (400) + Dining Out (200); Lifestyle = Travel (1000).
    assert by_cat["Food"] == Decimal("600.00")
    assert by_cat["Lifestyle"] == Decimal("1000.00")
    assert all(row["period_label"] == "Feb 2026" for row in series)


@pytest_asyncio.fixture
async def two_closed_periods_with_assets(session_factory):
    """Seed two closed periods with Cash + Brokerage assets and one memo asset.

    Period 1 (Jan 2026): +1000 Cash, +500 Brokerage, +200 memo.
    Period 2 (Feb 2026): +300 Cash, +700 Brokerage.

    Memo asset should never appear in asset_composition or asset_series.
    """
    async with session_factory() as session:
        p1 = Period(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status="closed",
            closed_at=datetime(2026, 2, 1),
        )
        p2 = Period(
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            status="closed",
            closed_at=datetime(2026, 3, 1),
        )
        session.add_all([p1, p2])
        session.add_all([
            Account(account_code=100101, account_name="Checking", account_type="Asset",
                    sub_category="Cash", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=111101, account_name="Brokerage", account_type="Asset",
                    sub_category="Brokerage", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=199101, account_name="Future Vehicle", account_type="Asset",
                    sub_category="Memo Vehicles", normal_balance="debit", is_memo=True, is_active=True),
            Account(account_code=300101, account_name="Opening Equity", account_type="Equity",
                    sub_category="Equity", normal_balance="credit", is_memo=False, is_active=True),
        ])
        await session.flush()

        def add_entry(period_id, entry_date, lines):
            entry = JournalEntry(
                entry_id=uuid.uuid4(),
                period_id=period_id,
                entry_date=entry_date,
                description="seed",
                source_type="manual",
            )
            session.add(entry)
            return entry

        e1 = add_entry(p1.period_id, date(2026, 1, 15), None)
        e2 = add_entry(p2.period_id, date(2026, 2, 15), None)
        await session.flush()

        session.add_all([
            # Period 1 — Cash +1000, Brokerage +500, Memo +200 (offset by Equity)
            JournalLine(line_id=uuid.uuid4(), entry_id=e1.entry_id,
                        account_code=100101, debit_amount=Decimal("1000"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=e1.entry_id,
                        account_code=111101, debit_amount=Decimal("500"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=e1.entry_id,
                        account_code=199101, debit_amount=Decimal("200"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=e1.entry_id,
                        account_code=300101, debit_amount=Decimal("0"), credit_amount=Decimal("1700")),
            # Period 2 — Cash +300, Brokerage +700 (offset by Equity)
            JournalLine(line_id=uuid.uuid4(), entry_id=e2.entry_id,
                        account_code=100101, debit_amount=Decimal("300"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=e2.entry_id,
                        account_code=111101, debit_amount=Decimal("700"), credit_amount=Decimal("0")),
            JournalLine(line_id=uuid.uuid4(), entry_id=e2.entry_id,
                        account_code=300101, debit_amount=Decimal("0"), credit_amount=Decimal("1000")),
        ])
        await session.commit()
        return p1.period_id, p2.period_id


@pytest.mark.asyncio
async def test_dashboard_asset_composition_excludes_memo(
    client: AsyncClient, two_closed_periods_with_assets
):
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()

    comp = body["asset_composition"]
    by_subcat = {row["sub_category"]: Decimal(row["amount"]) for row in comp}

    # Cumulative through Feb: Cash 1300, Brokerage 1200.
    assert by_subcat == {
        "Cash": Decimal("1300.00"),
        "Brokerage": Decimal("1200.00"),
    }
    assert "Memo Vehicles" not in by_subcat
    # Sorted descending by amount.
    assert comp[0]["sub_category"] == "Cash"


@pytest.mark.asyncio
async def test_dashboard_asset_series_per_period_per_subcat(
    client: AsyncClient, two_closed_periods_with_assets
):
    response = await client.get("/api/v1/dashboard")
    body = response.json()

    series = body["asset_series"]
    # Two periods × two non-memo sub_categories = 4 points; memo excluded.
    assert len(series) == 4
    indexed = {(r["period_label"], r["sub_category"]): Decimal(r["amount"]) for r in series}
    assert indexed[("Jan 2026", "Cash")] == Decimal("1000.00")
    assert indexed[("Jan 2026", "Brokerage")] == Decimal("500.00")
    assert indexed[("Feb 2026", "Cash")] == Decimal("1300.00")
    assert indexed[("Feb 2026", "Brokerage")] == Decimal("1200.00")
    assert not any(r["sub_category"] == "Memo Vehicles" for r in series)


@pytest.mark.asyncio
async def test_dashboard_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/dashboard")
    assert response.status_code == 401
