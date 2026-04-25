"""HTTP routes for the Period resource.

This is a server-rendered resource: browsers hit these routes via HTML forms,
so mutations respond with 303 redirects (POST/Redirect/GET) rather than JSON.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.services import period as period_service

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
    return templates.TemplateResponse(
        request,
        "periods/detail.html",
        {
            "period": period,
            "error": error,
            "next_status": period_service.next_status(period.status),
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
