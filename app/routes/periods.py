"""HTTP routes for the Period resource.

This is a server-rendered resource: browsers hit these routes via HTML forms,
so mutations respond with 303 redirects (POST/Redirect/GET) rather than JSON.
"""

import logging
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.account import Account
from app.services import document as document_service
from app.services import period as period_service
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

    return templates.TemplateResponse(
        request,
        "periods/detail.html",
        {
            "period": period,
            "error": error,
            "next_status": period_service.next_status(period.status),
            "documents": documents,
            "accounts": accounts,
            "balance_accounts": balance_accounts,
            "stated_balances": stated_balances,
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
