from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.account import Account

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/accounts", response_class=HTMLResponse)
async def chart_of_accounts(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    result = await db.scalars(
        select(Account).where(Account.is_active == True).order_by(Account.account_code)
    )
    accounts = result.all()

    grouped: dict[str, list[Account]] = {}
    type_order = ["Asset", "Liability", "Equity", "Income", "Expense", "Memo Asset*"]
    for t in type_order:
        grouped[t] = []
    for acct in accounts:
        grouped.setdefault(acct.account_type, []).append(acct)

    return templates.TemplateResponse(
        request,
        "accounts.html",
        {"grouped": grouped, "type_order": type_order},
    )
