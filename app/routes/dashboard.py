from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.services import period as period_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    current = await period_service.get_current_open_period(db)
    context = {
        "period": current,
        "metrics": {
            "income": 0.00,
            "expenses": 0.00,
            "net_income": 0.00,
            "total_assets": 0.00,
        },
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
