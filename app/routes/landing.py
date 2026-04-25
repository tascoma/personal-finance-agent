from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/workflows", response_class=HTMLResponse)
async def workflows(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html")
