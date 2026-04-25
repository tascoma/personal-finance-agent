from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    context = {
        "period": {"month": "April", "year": 2026, "status": "open"},
        "metrics": {
            "income": 0.00,
            "expenses": 0.00,
            "net_income": 0.00,
            "total_assets": 0.00,
        },
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
