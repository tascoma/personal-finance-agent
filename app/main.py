import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import configure_logging
from app.databases import init_db
from app.routes.accounts import router as accounts_router
from app.routes.api import (
    accounts as api_accounts,
    dashboard as api_dashboard,
    documents as api_documents,
    journal as api_journal,
    ledger as api_ledger,
    periods as api_periods,
    reconciliation as api_reconciliation,
    statements as api_statements,
    transactions as api_transactions,
)
from app.routes.dashboard import router as dashboard_router
from app.routes.ledger import router as ledger_router
from app.routes.periods import router as periods_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    await init_db()
    yield


app = FastAPI(title="Personal Finance Agent", lifespan=lifespan)

# JSON API router — must be mounted before the HTML routes and SPA catch-all
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(api_dashboard.router)
api_router.include_router(api_accounts.router)
api_router.include_router(api_ledger.router)
api_router.include_router(api_statements.router)
api_router.include_router(api_periods.router)
api_router.include_router(api_documents.router)
api_router.include_router(api_transactions.router)
api_router.include_router(api_journal.router)
api_router.include_router(api_reconciliation.router)
app.include_router(api_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard_router)
app.include_router(periods_router)
app.include_router(ledger_router)
app.include_router(accounts_router)

# SPA catch-all: serve frontend/dist/index.html for any unmatched path.
# Must be registered last so it never shadows API or HTML routes.
FRONTEND_DIST = "frontend/dist"
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIST}/assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(f"{FRONTEND_DIST}/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_excludes=["logs/*"],
    )
