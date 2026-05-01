import logging
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic_ai import Agent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_mortgage_extractor, get_paystub_extractor, get_statement_extractor
from app.models.account import Account
from app.models.raw_transaction import RawTransaction
from app.schemas.account import AccountRead
from app.schemas.api_responses import (
    PeriodDetailResponse,
    StatedBalanceItem,
    StatusUpdateRequest,
)
from app.schemas.document import DocumentRead
from app.schemas.period import PeriodCreate, PeriodRead
from app.services import document as document_service
from app.services import parse as parse_service
from app.services import period as period_service
from app.services import stated_balance as stated_balance_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["periods"])


@router.get("/periods", response_model=list[PeriodRead])
async def list_periods(
    db: AsyncSession = Depends(get_db_session),
) -> list[PeriodRead]:
    periods = await period_service.list_periods(db)
    return [PeriodRead.model_validate(p) for p in periods]


@router.post("/periods", response_model=PeriodRead, status_code=status.HTTP_201_CREATED)
async def create_period(
    body: PeriodCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PeriodRead:
    try:
        period = await period_service.create_period(db, year=body.year, month=body.month)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PeriodRead.model_validate(period)


@router.get("/periods/{period_id}", response_model=PeriodDetailResponse)
async def get_period_detail(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PeriodDetailResponse:
    period = await period_service.get_period(db, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    documents = await document_service.list_documents(db, period_id)

    accounts_result = await db.scalars(
        select(Account).where(Account.is_active.is_(True)).order_by(Account.account_code)
    )
    accounts = list(accounts_result.all())

    balance_accounts = await stated_balance_service.list_balance_accounts(db)
    balances = await stated_balance_service.list_balances(db, period_id)
    stated_balances = {row.account_code: str(row.stated_balance) for row in balances}

    txn_count = await db.scalar(
        select(func.count()).select_from(RawTransaction).where(RawTransaction.period_id == period_id)
    ) or 0
    staged_count = await db.scalar(
        select(func.count()).select_from(RawTransaction).where(
            RawTransaction.period_id == period_id, RawTransaction.status == "staged"
        )
    ) or 0
    approved_count = await db.scalar(
        select(func.count()).select_from(RawTransaction).where(
            RawTransaction.period_id == period_id, RawTransaction.status == "approved"
        )
    ) or 0
    posted_count = await db.scalar(
        select(func.count()).select_from(RawTransaction).where(
            RawTransaction.period_id == period_id, RawTransaction.status == "posted"
        )
    ) or 0
    unclassified_count = await db.scalar(
        select(func.count()).select_from(RawTransaction).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "staged",
            RawTransaction.classifier_confidence == Decimal("0"),
            RawTransaction.is_duplicate.is_(False),
        )
    ) or 0
    posted_doc_ids_result = await db.scalars(
        select(RawTransaction.document_id).where(
            RawTransaction.period_id == period_id,
            RawTransaction.status == "posted",
        ).distinct()
    )
    posted_doc_ids = [str(did) for did in posted_doc_ids_result.all() if did is not None]

    return PeriodDetailResponse(
        period=PeriodRead.model_validate(period),
        transaction_count=int(txn_count),
        staged_count=int(staged_count),
        approved_count=int(approved_count),
        posted_count=int(posted_count),
        unclassified_count=int(unclassified_count),
        documents=[DocumentRead.model_validate(d) for d in documents],
        accounts=[AccountRead.model_validate(a) for a in accounts],
        balance_accounts=[AccountRead.model_validate(a) for a in balance_accounts],
        stated_balances=stated_balances,
        has_pending_documents=any(d.parse_status == "pending" for d in documents),
        posted_doc_ids=posted_doc_ids,
        next_status=period_service.next_status(period.status),
        prev_status=period_service.prev_status(period.status),
    )


@router.post("/periods/{period_id}/status", response_model=PeriodRead)
async def update_period_status(
    period_id: uuid.UUID,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> PeriodRead:
    try:
        period = await period_service.update_status(db, period_id, body.new_status)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PeriodRead.model_validate(period)


@router.post("/periods/{period_id}/step-back", response_model=PeriodRead)
async def step_back_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PeriodRead:
    try:
        period = await period_service.step_back(db, period_id)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PeriodRead.model_validate(period)


@router.post("/periods/{period_id}/reopen", response_model=PeriodRead)
async def reopen_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PeriodRead:
    try:
        period = await period_service.reopen_period(db, period_id)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PeriodRead.model_validate(period)


@router.delete("/periods/{period_id}")
async def delete_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        await period_service.delete_period(db, period_id)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/periods/{period_id}/parse")
async def parse_all_documents(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    statement_agent: Agent = Depends(get_statement_extractor),
    paystub_agent: Agent = Depends(get_paystub_extractor),
    mortgage_agent: Agent = Depends(get_mortgage_extractor),
) -> dict:
    results = await parse_service.parse_period(db, period_id, statement_agent, paystub_agent, mortgage_agent)
    errors = [str(err) for err in results.values() if isinstance(err, str)]
    parsed = sum(1 for v in results.values() if not isinstance(v, str))
    return {"parsed": parsed, "errors": errors}


@router.post("/periods/{period_id}/balances")
async def upsert_balances(
    period_id: uuid.UUID,
    body: list[StatedBalanceItem],
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    valid_codes = {
        acct.account_code
        for acct in await stated_balance_service.list_balance_accounts(db)
    }
    for item in body:
        if item.account_code not in valid_codes:
            continue
        try:
            value = Decimal(item.stated_balance)
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"Invalid balance for account {item.account_code}")
        await stated_balance_service.upsert_balance(db, period_id, item.account_code, value)
    return {"ok": True}
