import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.services import dashboard as dashboard_service
from app.services import period as period_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    current = await period_service.get_current_open_period(db)
    data = await dashboard_service.compute_dashboard(db)

    chart_period_bars = json.dumps([
        {"label": b.label, "income": b.income, "expenses": b.expenses, "net": b.net}
        for b in data.period_bars
    ])
    chart_net_worth = json.dumps([
        {"label": p.label, "net_worth": p.net_worth}
        for p in data.net_worth_series
    ])
    chart_expense_cats = json.dumps([
        {"label": c.label, "amount": c.amount}
        for c in data.top_expense_categories
    ])

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "period": current,
            "data": data,
            "chart_period_bars": chart_period_bars,
            "chart_net_worth": chart_net_worth,
            "chart_expense_cats": chart_expense_cats,
        },
    )
