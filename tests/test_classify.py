"""Tests for the Journal phase — classify service + HTTP routes."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.classifier import ClassifierOutput, TxnSuggestion
from app.databases import Base
from app.dependencies import get_classifier_agent, get_db_session
from app.main import app
from app.models.account import Account
from app.models.document import Document
from app.models.raw_transaction import RawTransaction
from app.services import classify as classify_service
from app.services import period as period_service

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── stubs ─────────────────────────────────────────────────────────────────────


class _StubResult:
    def __init__(self, output) -> None:
        self.output = output


class _StubClassifier:
    def __init__(self, output: ClassifierOutput) -> None:
        self._output = output
        self.calls: list[str] = []

    async def run(self, prompt: str) -> _StubResult:
        self.calls.append(prompt)
        return _StubResult(self._output)


# ── fixtures ──────────────────────────────────────────────────────────────────


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
            Account(account_code=200101, account_name="Mastercard", account_type="Liability",
                    sub_category="Credit Cards", normal_balance="credit", is_memo=False, is_active=True),
            Account(account_code=520101, account_name="Groceries", account_type="Expense",
                    sub_category="Food", normal_balance="debit", is_memo=False, is_active=True),
            Account(account_code=400101, account_name="Salary - Regular", account_type="Income",
                    sub_category="Earned", normal_balance="credit", paystub_mapping="REGULAR EARNING",
                    is_memo=False, is_active=True),
        ])
        await session.commit()
    yield factory
    await eng.dispose()


@pytest_asyncio.fixture
async def open_period(session_factory):
    async with session_factory() as session:
        period = await period_service.create_period(session, 2026, 1)
    return period


@pytest_asyncio.fixture
async def journal_period(session_factory):
    async with session_factory() as session:
        period = await period_service.create_period(session, 2026, 1)
    async with session_factory() as session:
        await period_service.update_status(session, period.period_id, "pending_review")
    async with session_factory() as session:
        period = await period_service.update_status(session, period.period_id, "pending_close")
    return period


@pytest_asyncio.fixture
async def statement_doc(session_factory, open_period):
    async with session_factory() as session:
        doc = Document(
            period_id=open_period.period_id,
            document_type="bank_statement",
            file_name="bank.csv",
            file_path="/tmp/bank.csv",
            source_account_code=100101,
            parse_status="complete",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
    return doc


@pytest_asyncio.fixture
async def paystub_doc(session_factory, open_period):
    async with session_factory() as session:
        doc = Document(
            period_id=open_period.period_id,
            document_type="paystub",
            file_name="paystub.pdf",
            file_path="/tmp/paystub.pdf",
            source_account_code=100101,
            parse_status="complete",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
    return doc


async def _add_staged_txn(
    session_factory,
    doc: Document,
    description: str,
    amount: Decimal,
    confidence: Decimal = Decimal("0"),
    is_duplicate: bool = False,
) -> RawTransaction:
    async with session_factory() as session:
        txn = RawTransaction(
            document_id=doc.document_id,
            period_id=doc.period_id,
            txn_date=date(2026, 1, 10),
            description=description,
            amount=amount,
            classifier_confidence=confidence,
            is_flagged=False,
            is_duplicate=is_duplicate,
            status="staged",
        )
        session.add(txn)
        await session.commit()
        await session.refresh(txn)
    return txn


# ── service-level tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_updates_suggestion(session_factory, statement_doc, open_period):
    txn = await _add_staged_txn(session_factory, statement_doc, "GROCERY STORE", Decimal("-45.00"))
    short_id = txn.raw_txn_id.hex[:8]
    stub = _StubClassifier(ClassifierOutput(suggestions=[
        TxnSuggestion(id=short_id, account_code=520101, confidence=0.95, reasoning="Grocery store"),
    ]))

    async with session_factory() as session:
        count = await classify_service.classify_period(session, open_period.period_id, stub)

    assert count == 1
    async with session_factory() as session:
        updated = await session.get(RawTransaction, txn.raw_txn_id)
    assert updated.suggested_account_code == 520101
    assert updated.classifier_confidence == Decimal("0.95")
    assert updated.is_flagged is False


@pytest.mark.asyncio
async def test_classify_flags_low_confidence(session_factory, statement_doc, open_period):
    txn = await _add_staged_txn(session_factory, statement_doc, "MYSTERY CHARGE", Decimal("-10.00"))
    short_id = txn.raw_txn_id.hex[:8]
    stub = _StubClassifier(ClassifierOutput(suggestions=[
        TxnSuggestion(id=short_id, account_code=520101, confidence=0.5, reasoning="Unclear"),
    ]))

    async with session_factory() as session:
        await classify_service.classify_period(session, open_period.period_id, stub)

    async with session_factory() as session:
        updated = await session.get(RawTransaction, txn.raw_txn_id)
    assert updated.is_flagged is True


@pytest.mark.asyncio
async def test_classify_skips_paystub_txns(session_factory, paystub_doc, open_period):
    await _add_staged_txn(session_factory, paystub_doc, "REGULAR EARNING", Decimal("3000.00"),
                          confidence=Decimal("1.000"))
    stub = _StubClassifier(ClassifierOutput(suggestions=[]))

    async with session_factory() as session:
        count = await classify_service.classify_period(session, open_period.period_id, stub)

    assert count == 0
    assert stub.calls == []


@pytest.mark.asyncio
async def test_classify_skips_already_classified(session_factory, statement_doc, open_period):
    await _add_staged_txn(session_factory, statement_doc, "COFFEE", Decimal("-5.00"),
                          confidence=Decimal("0.90"))
    stub = _StubClassifier(ClassifierOutput(suggestions=[]))

    async with session_factory() as session:
        count = await classify_service.classify_period(session, open_period.period_id, stub)

    assert count == 0
    assert stub.calls == []


@pytest.mark.asyncio
async def test_classify_skips_duplicates(session_factory, statement_doc, open_period):
    await _add_staged_txn(session_factory, statement_doc, "DUP CHARGE", Decimal("-5.00"),
                          is_duplicate=True)
    stub = _StubClassifier(ClassifierOutput(suggestions=[]))

    async with session_factory() as session:
        count = await classify_service.classify_period(session, open_period.period_id, stub)

    assert count == 0


@pytest.mark.asyncio
async def test_classify_ignores_unknown_account_code(session_factory, statement_doc, open_period):
    txn = await _add_staged_txn(session_factory, statement_doc, "UNKNOWN MERCHANT", Decimal("-20.00"))
    short_id = txn.raw_txn_id.hex[:8]
    stub = _StubClassifier(ClassifierOutput(suggestions=[
        TxnSuggestion(id=short_id, account_code=999999, confidence=0.8, reasoning="?"),
    ]))

    async with session_factory() as session:
        count = await classify_service.classify_period(session, open_period.period_id, stub)

    assert count == 0
    async with session_factory() as session:
        unchanged = await session.get(RawTransaction, txn.raw_txn_id)
    assert unchanged.suggested_account_code is None
    assert unchanged.is_flagged is True


# ── HTTP route tests ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_db():
        async with session_factory() as session:
            yield session

    def noop_classifier():
        return _StubClassifier(ClassifierOutput(suggestions=[]))

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_classifier_agent] = noop_classifier
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_journal_page_renders(client, journal_period):
    response = await client.get(f"/periods/{journal_period.period_id}/journal")
    assert response.status_code == 200
    assert "Ledger" in response.text


@pytest.mark.asyncio
async def test_classify_route_redirects_to_journal(client, journal_period):
    response = await client.post(f"/periods/{journal_period.period_id}/classify")
    assert response.status_code == 200
    assert "Ledger" in response.text


@pytest.mark.asyncio
async def test_classify_route_blocked_outside_journal_phase(client, open_period):
    response = await client.post(f"/periods/{open_period.period_id}/classify")
    assert response.status_code == 200
    assert "journal phase" in response.text.lower()


@pytest.mark.asyncio
async def test_approve_reject_route(client, journal_period, session_factory):
    async with session_factory() as session:
        doc = Document(
            period_id=journal_period.period_id,
            document_type="bank_statement",
            file_name="bank.csv",
            file_path="/tmp/bank.csv",
            source_account_code=100101,
            parse_status="complete",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

    txn = await _add_staged_txn(session_factory, doc, "MARKET", Decimal("-30.00"))

    response = await client.post(
        f"/periods/{journal_period.period_id}/transactions/{txn.raw_txn_id}/approve"
    )
    assert response.status_code == 200
    async with session_factory() as session:
        updated = await session.get(RawTransaction, txn.raw_txn_id)
    assert updated.status == "approved"

    response = await client.post(
        f"/periods/{journal_period.period_id}/transactions/{txn.raw_txn_id}/reject"
    )
    assert response.status_code == 200
    async with session_factory() as session:
        updated = await session.get(RawTransaction, txn.raw_txn_id)
    assert updated.status == "rejected"


@pytest.mark.asyncio
async def test_update_account_route(client, journal_period, session_factory):
    async with session_factory() as session:
        doc = Document(
            period_id=journal_period.period_id,
            document_type="bank_statement",
            file_name="bank.csv",
            file_path="/tmp/bank.csv",
            source_account_code=100101,
            parse_status="complete",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

    txn = await _add_staged_txn(session_factory, doc, "SHOP", Decimal("-12.00"))

    response = await client.post(
        f"/periods/{journal_period.period_id}/transactions/{txn.raw_txn_id}/account",
        data={"account_code": "520101"},
    )
    assert response.status_code == 200
    async with session_factory() as session:
        updated = await session.get(RawTransaction, txn.raw_txn_id)
    assert updated.suggested_account_code == 520101
    assert updated.is_flagged is False
