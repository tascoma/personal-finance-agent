import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import configure_logging
from app.databases import init_db
from app.routes import (
    transactions as api_transactions,
)
from app.routes import accounts as api_accounts, dashboard as api_dashboard, documents as api_documents, journal as api_journal, ledger as api_ledger, periods as api_periods, reconciliation as api_reconciliation, statements as api_statements


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    await init_db()
    yield
    from app.databases import engine as _engine
    await _engine.dispose()


app = FastAPI(title="Personal Finance Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", include_in_schema=False)
async def health_check() -> dict:
    return {"status": "ok"}


# JSON API router — must be mounted before the SPA catch-all
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

# SPA catch-all: serve frontend/dist/index.html for any unmatched non-API path.
# Must be registered last so it never shadows API routes.
FRONTEND_DIST = str(Path(__file__).resolve().parents[2] / "frontend" / "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIST}/assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse | Response:
        if full_path.startswith("api/"):
            return Response(status_code=404)
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
