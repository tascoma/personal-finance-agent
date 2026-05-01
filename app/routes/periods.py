"""HTTP routes for the Period resource.

This is a server-rendered resource: browsers hit these routes via HTML forms,
so mutations respond with 303 redirects (POST/Redirect/GET) rather than JSON.
"""

import logging
import uuid
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai import Agent
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_classifier_agent,
    get_db_session,
    get_mortgage_extractor,
    get_paystub_extractor,
    get_reconciliation_agent,
    get_statement_extractor,
)
from app.agents.reconciliation import AccountGap, ReconciliationAnalysis
from app.models.account import Account
from app.models.document import Document
from app.models.journal import JournalEntry, JournalLine
from app.models.raw_transaction import RawTransaction
from app.models.reconciliation import Reconciliation
from app.models.review_queue import ReviewQueue
from app.schemas.reconciliation import ReconciliationDetail
from app.services.file_readers import ParseError
from app.services import classify as classify_service
from app.services import document as document_service
from app.services import journal as journal_service
from app.services import parse as parse_service
from app.services import period as period_service
from app.services import reconciliation as reconciliation_service
from app.services import stated_balance as stated_balance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/periods", tags=["periods"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_periods(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    error: str | None = None,
) -> HTMLResponse:
    periods = await period_service.list_periods(db)
    return templates.TemplateResponse(
        request,
        "periods/list.html",
        {"periods": periods, "error": error},
    )


@router.post("", response_class=HTMLResponse)
async def create_period(
    year: int = Form(...),
    month: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        period = await period_service.create_period(db, year=year, month=month)
    except period_service.PeriodError as exc:
        logger.warning("Create period failed: %s", exc)
        return RedirectResponse(
            url=f"/periods?error={exc}", status_code=status.HTTP_303_SEE_OTHER
        )
    return RedirectResponse(
        url=f"/periods/{period.period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{period_id}", response_class=HTMLResponse)
async def period_detail(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    error: str | None = None,
) -> HTMLResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    documents = await document_service.list_documents(db, period_id)

    accounts_result = await db.scalars(
        select(Account)
        .where(Account.is_active == True)  # noqa: E712
        .order_by(Account.account_code)
    )
    accounts = accounts_result.all()

    balance_accounts = await stated_balance_service.list_balance_accounts(db)
    balances = await stated_balance_service.list_balances(db, period_id)
    stated_balances = {row.account_code: row.stated_balance for row in balances}

    has_pending = any(d.parse_status == "pending" for d in documents)
    txn_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.period_id == period_id)
    )
    staged_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "staged")
    )
    approved_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "approved")
    )
    posted_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "posted")
    )
    unclassified_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "staged",
            RawTransaction.classifier_confidence == Decimal("0"),
            RawTransaction.is_duplicate.is_(False),
        )
    )
    posted_doc_ids_result = await db.scalars(
        select(RawTransaction.document_id)
        .where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "posted",
        )
        .distinct()
    )
    posted_doc_ids: set[uuid.UUID] = set(posted_doc_ids_result.all())

    return templates.TemplateResponse(
        request,
        "periods/detail.html",
        {
            "period": period,
            "error": error,
            "next_status": period_service.next_status(period.status),
            "prev_status": period_service.prev_status(period.status),
            "documents": documents,
            "accounts": accounts,
            "balance_accounts": balance_accounts,
            "stated_balances": stated_balances,
            "has_pending_documents": has_pending,
            "transaction_count": int(txn_count or 0),
            "staged_count": int(staged_count or 0),
            "approved_count": int(approved_count or 0),
            "posted_count": int(posted_count or 0),
            "unclassified_count": int(unclassified_count or 0),
            "posted_doc_ids": posted_doc_ids,
        },
    )


@router.post("/{period_id}/status")
async def update_period_status(
    period_id: uuid.UUID,
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await period_service.update_status(db, period_id, new_status)
    except period_service.PeriodError as exc:
        logger.warning("Status update failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/step-back")
async def step_back_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await period_service.step_back(db, period_id)
    except period_service.PeriodError as exc:
        logger.warning("Step back failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/reopen")
async def reopen_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await period_service.reopen_period(db, period_id)
    except period_service.PeriodError as exc:
        logger.warning("Reopen failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/delete")
async def delete_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await period_service.delete_period(db, period_id)
    except period_service.PeriodError as exc:
        logger.warning("Delete failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/periods", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{period_id}/documents")
async def upload_document(
    period_id: uuid.UUID,
    document_type: str = Form(...),
    source_account_code: int | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await document_service.save_upload(
            db,
            period_id=period_id,
            document_type=document_type,
            source_account_code=source_account_code,
            upload=file,
        )
    except document_service.DocumentError as exc:
        logger.warning("Document upload failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/documents/{document_id}/delete")
async def delete_document_route(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await document_service.delete_document(db, document_id)
    except document_service.DocumentError as exc:
        logger.warning("Document delete failed for %s: %s", document_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/balances")
async def upsert_balances(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    form = await request.form()
    valid_codes = {
        acct.account_code
        for acct in await stated_balance_service.list_balance_accounts(db)
    }

    try:
        for field, raw_value in form.multi_items():
            if not field.isdigit():
                continue
            code = int(field)
            if code not in valid_codes:
                continue
            value = (raw_value or "").strip() if isinstance(raw_value, str) else ""
            if not value:
                continue
            try:
                amount = Decimal(value)
            except InvalidOperation as exc:
                raise stated_balance_service.BalanceError(
                    f"Invalid amount for account {code}: {value}"
                ) from exc
            await stated_balance_service.upsert_balance(
                db,
                period_id=period_id,
                account_code=code,
                stated_balance=amount,
            )
    except stated_balance_service.BalanceError as exc:
        logger.warning("Balance upsert failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/documents/{document_id}/parse")
async def parse_document_route(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    statement_agent: Agent = Depends(get_statement_extractor),
    paystub_agent: Agent = Depends(get_paystub_extractor),
    mortgage_agent: Agent = Depends(get_mortgage_extractor),
) -> RedirectResponse:
    try:
        await parse_service.parse_document(
            db, document_id, statement_agent, paystub_agent, mortgage_agent
        )
    except ParseError as exc:
        logger.warning("Parse failed for %s: %s", document_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/documents/{document_id}/unpost")
async def unpost_document_route(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}?error=Unpost is only available in the journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    count = await journal_service.unpost_document(db, document_id, period_id)
    logger.info("Unposted %d transactions for document %s", count, document_id)
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/documents/{document_id}/source-account")
async def update_document_source_account_route(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    source_account_code: str = Form(""),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status not in ("open", "pending_close"):
        return RedirectResponse(
            url=f"/periods/{period_id}?error=Period is not open for edits",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    code: int | None = int(source_account_code) if source_account_code.strip() else None
    try:
        await document_service.update_source_account(db, document_id, code)
    except document_service.DocumentError as exc:
        logger.warning("Source account update failed for document %s: %s", document_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/parse")
async def parse_period_route(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    statement_agent: Agent = Depends(get_statement_extractor),
    paystub_agent: Agent = Depends(get_paystub_extractor),
    mortgage_agent: Agent = Depends(get_mortgage_extractor),
) -> RedirectResponse:
    results = await parse_service.parse_period(
        db, period_id, statement_agent, paystub_agent, mortgage_agent
    )
    failures = [(doc_id, err) for doc_id, err in results.items() if isinstance(err, str)]
    if failures:
        for doc_id, err in failures:
            logger.warning("Parse failed for document %s in period %s: %s", doc_id, period_id, err)
        msg = "; ".join(err for _, err in failures[:3])
        return RedirectResponse(
            url=f"/periods/{period_id}?error=Parse errors: {msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{period_id}/transactions", response_class=HTMLResponse)
async def list_period_transactions(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    error: str | None = None,
) -> HTMLResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    txn_result = await db.scalars(
        select(RawTransaction)
        .where(RawTransaction.period_id == period_id)
        .order_by(RawTransaction.txn_date, RawTransaction.created_at)
    )
    transactions = txn_result.all()

    accounts_result = await db.scalars(
        select(Account).where(Account.is_active == True).order_by(Account.account_code)  # noqa: E712
    )
    accounts = accounts_result.all()
    accounts_by_code = {a.account_code: a for a in accounts}

    return templates.TemplateResponse(
        request,
        "periods/transactions.html",
        {
            "period": period,
            "error": error,
            "transactions": transactions,
            "accounts": accounts,
            "accounts_by_code": accounts_by_code,
        },
    )


@router.post("/{period_id}/transactions")
async def add_manual_transaction(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status not in ("open", "pending_close"):
        return RedirectResponse(
            url=f"/periods/{period_id}/transactions?error=Period is not open for new transactions",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    form = await request.form()
    txn_dates = form.getlist("txn_date")
    descriptions = form.getlist("description")
    amounts = form.getlist("amount")
    account_codes = form.getlist("account_code")
    redirect_to = str(form.get("redirect_to", "transactions"))

    rows = list(zip(txn_dates, descriptions, amounts, account_codes))
    if not rows:
        return RedirectResponse(
            url=f"/periods/{period_id}/transactions?error=No transactions submitted",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    manual_doc = await document_service.get_or_create_manual_document(db, period_id)

    added = 0
    for txn_date_str, description, amount_str, account_code_str in rows:
        if not (txn_date_str and description and amount_str and account_code_str):
            continue
        try:
            txn_date = date_type.fromisoformat(str(txn_date_str))
            amount = Decimal(str(amount_str))
            account_code = int(account_code_str)
        except (ValueError, InvalidOperation) as exc:
            return RedirectResponse(
                url=f"/periods/{period_id}/transactions?error=Invalid value: {exc}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        account = await db.get(Account, account_code)
        if account is None:
            return RedirectResponse(
                url=f"/periods/{period_id}/transactions?error=Unknown account {account_code}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        db.add(
            RawTransaction(
                document_id=manual_doc.document_id,
                period_id=period_id,
                txn_date=txn_date,
                description=description.strip(),
                amount=amount,
                suggested_account_code=account_code,
                classifier_confidence=Decimal("1.000"),
                is_flagged=False,
                is_duplicate=False,
                status="staged",
            )
        )
        added += 1

    await db.commit()
    logger.info("Added %d manual transaction(s) for period %s", added, period_id)

    dest = f"/periods/{period_id}" if redirect_to == "detail" else f"/periods/{period_id}/transactions"
    return RedirectResponse(url=dest, status_code=status.HTTP_303_SEE_OTHER)


# ── Journal phase ─────────────────────────────────────────────────────────────


@router.get("/{period_id}/journal", response_class=HTMLResponse)
async def journal_page(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    error: str | None = None,
) -> HTMLResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    accounts_result = await db.scalars(
        select(Account).where(Account.is_active == True).order_by(Account.account_code)  # noqa: E712
    )
    accounts = accounts_result.all()
    accounts_by_code = {a.account_code: a for a in accounts}

    staged_result = await db.scalars(
        select(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "staged")
        .order_by(RawTransaction.txn_date, RawTransaction.created_at)
    )
    staged = staged_result.all()

    approved_result = await db.scalars(
        select(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "approved")
        .order_by(RawTransaction.txn_date, RawTransaction.created_at)
    )
    approved = approved_result.all()

    entries_result = await db.scalars(
        select(JournalEntry)
        .where(JournalEntry.period_id == period_id)
        .order_by(JournalEntry.entry_date, JournalEntry.created_at)
    )
    entries = entries_result.all()

    entry_ids = [e.entry_id for e in entries]
    lines_by_entry: dict[uuid.UUID, list[JournalLine]] = {e.entry_id: [] for e in entries}
    if entry_ids:
        lines_result = await db.scalars(
            select(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
        )
        for line in lines_result.all():
            lines_by_entry[line.entry_id].append(line)

    has_unclassified = any(
        t.classifier_confidence == Decimal("0") and not t.is_duplicate
        for t in staged
    )

    # Load documents that have approved transactions so we can warn about missing source accounts
    approved_doc_ids = {t.document_id for t in approved}
    docs_missing_source: list[Document] = []
    if approved_doc_ids:
        docs_result = await db.scalars(
            select(Document).where(
                Document.document_id.in_(approved_doc_ids),
                Document.source_account_code.is_(None),
            )
        )
        docs_missing_source = list(docs_result.all())

    return templates.TemplateResponse(
        request,
        "periods/journal.html",
        {
            "period": period,
            "error": error,
            "accounts": accounts,
            "accounts_by_code": accounts_by_code,
            "staged": staged,
            "approved": approved,
            "entries": entries,
            "lines_by_entry": lines_by_entry,
            "has_unclassified": has_unclassified,
            "docs_missing_source": docs_missing_source,
        },
    )


@router.post("/{period_id}/classify")
async def classify_period_route(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    classifier_agent: Agent = Depends(get_classifier_agent),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        count = await classify_service.classify_period(db, period_id, classifier_agent)
    except Exception as exc:
        logger.error("Classify failed for period %s: %s", period_id, exc, exc_info=True)
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    logger.info("Classified %d transactions in period %s", count, period_id)
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/post")
async def post_period_route(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    approved_count = await db.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.period_id == period_id, RawTransaction.status == "approved")
    )
    try:
        count = await journal_service.post_period(db, period_id)
    except journal_service.JournalError as exc:
        logger.warning("Post failed for period %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    logger.info("Posted %d entries for period %s", count, period_id)
    if count == 0 and approved_count:
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Nothing posted — one or more documents are missing a source account. Set the deposit account for each document below.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/documents/{document_id}/source-account")
async def update_document_source_account(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    source_account_code: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    doc = await db.get(Document, document_id)
    if doc is None or doc.period_id != period_id:
        raise HTTPException(status_code=404, detail="Document not found")
    acct = await db.get(Account, source_account_code)
    if acct is None:
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Unknown account {source_account_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    doc.source_account_code = source_account_code
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/{raw_txn_id}/approve")
async def approve_transaction(
    period_id: uuid.UUID,
    raw_txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    txn = await db.get(RawTransaction, raw_txn_id)
    if txn is None or txn.period_id != period_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    txn.status = "approved"
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/{raw_txn_id}/unapprove")
async def unapprove_transaction(
    period_id: uuid.UUID,
    raw_txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    txn = await db.get(RawTransaction, raw_txn_id)
    if txn is None or txn.period_id != period_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    txn.status = "staged"
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/approve-all-staged")
async def approve_all_staged_transactions(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    staged_txns = await db.scalars(
        select(RawTransaction).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "staged",
        )
    )
    for txn in staged_txns.all():
        txn.status = "approved"
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/unapprove-all")
async def unapprove_all_transactions(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    approved_txns = await db.scalars(
        select(RawTransaction).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "approved",
        )
    )
    for txn in approved_txns.all():
        txn.status = "staged"
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/{raw_txn_id}/reject")
async def reject_transaction(
    period_id: uuid.UUID,
    raw_txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    txn = await db.get(RawTransaction, raw_txn_id)
    if txn is None or txn.period_id != period_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.execute(delete(ReviewQueue).where(ReviewQueue.raw_txn_id == raw_txn_id))
    await db.delete(txn)
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/clear-all")
async def clear_all_transactions(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    txn_ids_result = await db.scalars(
        select(RawTransaction.raw_txn_id).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status.in_(["staged", "approved"]),
        )
    )
    txn_ids = txn_ids_result.all()
    if txn_ids:
        await db.execute(delete(ReviewQueue).where(ReviewQueue.raw_txn_id.in_(txn_ids)))
        await db.execute(
            delete(RawTransaction).where(RawTransaction.raw_txn_id.in_(txn_ids))
        )
        await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/reject-all-staged")
async def reject_all_staged_transactions(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    staged_ids_result = await db.scalars(
        select(RawTransaction.raw_txn_id).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "staged",
        )
    )
    staged_ids = staged_ids_result.all()
    if staged_ids:
        await db.execute(delete(ReviewQueue).where(ReviewQueue.raw_txn_id.in_(staged_ids)))
        await db.execute(
            delete(RawTransaction).where(RawTransaction.raw_txn_id.in_(staged_ids))
        )
        await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/journal/entries")
async def create_manual_journal_entry(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status == "closed":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is closed",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    form = await request.form()
    entry_date_str = str(form.get("entry_date", "")).strip()
    description = str(form.get("description", "")).strip()
    source_type = str(form.get("source_type", "manual")).strip()

    try:
        entry_date = date_type.fromisoformat(entry_date_str)
    except ValueError:
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Invalid date",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    account_codes = form.getlist("account_code")
    debits = form.getlist("debit")
    credits_ = form.getlist("credit")
    memos = form.getlist("memo")

    lines: list[tuple[int, Decimal, Decimal, str | None]] = []
    try:
        for i, code in enumerate(account_codes):
            if not code:
                continue
            debit = Decimal(debits[i] or "0") if i < len(debits) else Decimal("0")
            credit = Decimal(credits_[i] or "0") if i < len(credits_) else Decimal("0")
            memo: str | None = memos[i].strip() or None if i < len(memos) else None
            lines.append((int(code), debit, credit, memo))
    except (InvalidOperation, ValueError) as exc:
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Invalid amount: {exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        await journal_service.create_manual_entry(
            db, period_id, entry_date, description, source_type, lines
        )
    except journal_service.JournalError as exc:
        logger.warning("Manual journal entry failed for period %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    logger.info("Manual journal entry created for period %s", period_id)
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/journal/entries/{entry_id}/delete")
async def delete_journal_entry(
    period_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None or period.status == "closed":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Cannot+delete+entries+from+a+closed+period",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await journal_service.delete_entry(db, entry_id, period_id)
    except journal_service.JournalError as exc:
        logger.warning("Delete journal entry failed for %s: %s", entry_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/transactions/{raw_txn_id}/account")
async def update_transaction_account(
    period_id: uuid.UUID,
    raw_txn_id: uuid.UUID,
    account_code: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "pending_close":
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Period is not in journal phase",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    txn = await db.get(RawTransaction, raw_txn_id)
    if txn is None or txn.period_id != period_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    acct = await db.get(Account, account_code)
    if acct is None:
        return RedirectResponse(
            url=f"/periods/{period_id}/journal?error=Unknown account {account_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    txn.suggested_account_code = account_code
    txn.is_flagged = False
    await db.commit()
    return RedirectResponse(
        url=f"/periods/{period_id}/journal", status_code=status.HTTP_303_SEE_OTHER
    )


# ── Reconciliation ──────────────────────────────────────────────────────────


async def _build_recon_details(
    db: AsyncSession,
    period_id: uuid.UUID,
) -> tuple[list[ReconciliationDetail], bool, bool]:
    """Load Reconciliation rows and merge with computed breakdown.

    Returns (details, has_gaps, has_investment_gaps).
    """
    from app.models.period import Period  # avoid circular at module level

    recon_rows = (await db.scalars(
        select(Reconciliation)
        .where(Reconciliation.period_id == period_id)
        .order_by(Reconciliation.account_code)
    )).all()

    if not recon_rows:
        return [], False, False

    period = await db.get(Period, period_id)
    if period is None:
        return [], False, False

    balances = await reconciliation_service.compute_account_balances(db, period)

    account_codes = [r.account_code for r in recon_rows]
    accts = (await db.scalars(
        select(Account).where(Account.account_code.in_(account_codes))
    )).all()
    acct_by_code = {a.account_code: a for a in accts}

    details: list[ReconciliationDetail] = []
    for row in recon_rows:
        b = balances.get(row.account_code, {})
        acct = acct_by_code.get(row.account_code)
        details.append(ReconciliationDetail(
            recon_id=row.recon_id,
            period_id=row.period_id,
            account_code=row.account_code,
            account_name=b.get("account_name") or (acct.account_name if acct else str(row.account_code)),
            is_investment=b.get("is_investment", False),
            beginning_balance=b.get("beginning_balance", Decimal("0")),
            period_net_change=b.get("period_net_change", Decimal("0")),
            computed_balance=row.computed_balance,
            stated_balance=row.stated_balance,
            gap=row.gap,
            status=row.status,
            run_at=row.run_at,
        ))

    has_gaps = any(d.status != "reconciled" for d in details)
    has_investment_gaps = any(d.is_investment and d.status != "reconciled" for d in details)
    return details, has_gaps, has_investment_gaps


@router.get("/{period_id}/reconcile", response_class=HTMLResponse)
async def reconcile_page(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    error: str | None = None,
    success: str | None = None,
) -> HTMLResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    details, has_gaps, has_investment_gaps = await _build_recon_details(db, period_id)
    has_non_investment_gaps = any(
        not d.is_investment and d.status != "reconciled" for d in details
    )
    temp_preview = await reconciliation_service.compute_temp_account_preview(db, period)
    equity_preview = await reconciliation_service.compute_equity_rollup_preview(db, period)

    return templates.TemplateResponse(
        request,
        "periods/reconcile.html",
        {
            "period": period,
            "error": error,
            "success": success,
            "details": details,
            "ran": bool(details),
            "has_gaps": has_gaps,
            "has_investment_gaps": has_investment_gaps,
            "has_non_investment_gaps": has_non_investment_gaps,
            "analysis": None,
            "analysis_by_code": {},
            "temp_preview": temp_preview,
            "equity_preview": equity_preview,
        },
    )


@router.post("/{period_id}/reconcile")
async def run_reconcile(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await reconciliation_service.run_reconciliation(db, period_id)
    except reconciliation_service.ReconciliationError as exc:
        logger.warning("Reconciliation failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}/reconcile",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{period_id}/reconcile/post-unrealized")
async def post_unrealized_gl(
    period_id: uuid.UUID,
    account_code: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    recon_row = (await db.scalars(
        select(Reconciliation).where(
            Reconciliation.period_id == period_id,
            Reconciliation.account_code == account_code,
        )
    )).first()
    if recon_row is None:
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error=No reconciliation row for account {account_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await reconciliation_service.create_unrealized_gl_entry(
            db, period_id, account_code, recon_row.gap
        )
    except reconciliation_service.ReconciliationError as exc:
        logger.warning("Unrealized G/L post failed: %s", exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    await reconciliation_service.run_reconciliation(db, period_id)
    acct = await db.get(Account, account_code)
    acct_label = acct.account_name if acct else str(account_code)
    return RedirectResponse(
        url=f"/periods/{period_id}/reconcile?success=Unrealized+G%2FL+entry+posted+for+{acct_label}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{period_id}/reconcile/post-closing")
async def post_closing(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await reconciliation_service.post_closing_entries(db, period_id)
    except reconciliation_service.ReconciliationError as exc:
        logger.warning("Closing entries post failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}/reconcile?success=Closing+entries+posted",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{period_id}/reconcile/post-equity-rollup")
async def post_equity_rollup(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await reconciliation_service.post_equity_rollup(db, period_id)
    except reconciliation_service.ReconciliationError as exc:
        logger.warning("Equity rollup failed for %s: %s", period_id, exc)
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/periods/{period_id}/reconcile?success=Equity+rollup+posted",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{period_id}/reconcile/analyze", response_class=HTMLResponse)
async def analyze_reconciliation(
    period_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    recon_agent: Agent = Depends(get_reconciliation_agent),
) -> HTMLResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    # Only analyze non-investment gaps (investment gaps have a known cause)
    gapped_rows = (await db.scalars(
        select(Reconciliation).where(
            Reconciliation.period_id == period_id,
            Reconciliation.status != "reconciled",
        )
    )).all()

    # Filter to non-investment accounts
    non_investment_gapped: list[Reconciliation] = []
    for row in gapped_rows:
        acct = await db.get(Account, row.account_code)
        if acct and acct.sub_category not in reconciliation_service._INVESTMENT_SUBCATEGORIES:
            non_investment_gapped.append(row)

    if not non_investment_gapped:
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Build AccountGap inputs with top-5 entry descriptions per account
    gap_inputs: list[AccountGap] = []
    for row in non_investment_gapped:
        acct = await db.get(Account, row.account_code)
        desc_rows = (await db.scalars(
            select(JournalEntry.description)
            .join(JournalLine, JournalLine.entry_id == JournalEntry.entry_id)
            .where(
                JournalEntry.period_id == period_id,
                JournalLine.account_code == row.account_code,
            )
            .order_by(JournalEntry.entry_date.desc())
            .limit(5)
        )).all()
        gap_inputs.append(AccountGap(
            account_code=row.account_code,
            account_name=acct.account_name if acct else str(row.account_code),
            computed_balance=row.computed_balance,
            stated_balance=row.stated_balance,
            gap=row.gap,
            recent_entry_descriptions=list(desc_rows),
        ))

    prompt = (
        f"Period: {period.period_start.strftime('%B %Y')}. "
        f"Analyze these {len(gap_inputs)} non-investment reconciliation gap(s): "
        + str([g.model_dump() for g in gap_inputs])
    )
    try:
        result = await recon_agent.run(prompt)
    except Exception as exc:
        logger.error(
            "Reconciliation analysis agent failed for period %s: %s",
            period_id,
            exc,
            exc_info=True,
        )
        return RedirectResponse(
            url=f"/periods/{period_id}/reconcile?error=Analysis failed: {exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    analysis: ReconciliationAnalysis = result.output
    analysis_by_code = {a.account_code: a for a in analysis.accounts}

    details, has_gaps, has_investment_gaps = await _build_recon_details(db, period_id)
    has_non_investment_gaps = any(
        not d.is_investment and d.status != "reconciled" for d in details
    )
    temp_preview = await reconciliation_service.compute_temp_account_preview(db, period)
    equity_preview = await reconciliation_service.compute_equity_rollup_preview(db, period)

    return templates.TemplateResponse(
        request,
        "periods/reconcile.html",
        {
            "period": period,
            "error": None,
            "success": None,
            "details": details,
            "ran": True,
            "has_gaps": has_gaps,
            "has_investment_gaps": has_investment_gaps,
            "has_non_investment_gaps": has_non_investment_gaps,
            "analysis": analysis,
            "analysis_by_code": analysis_by_code,
            "temp_preview": temp_preview,
            "equity_preview": equity_preview,
        },
    )
