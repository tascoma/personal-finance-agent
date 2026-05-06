# CLAUDE.md

Practice project for building a full-stack web app with a FastAPI backend and React frontend, backed by an AI agent pipeline.

## Behavior

- **Simplicity first.** Prefer the smallest solution that works. No premature abstractions, no speculative flexibility, no helpers that wrap a one-liner.
- **Test after implementation.** After any code change, run the relevant tests (or write one if none exists for the path) before reporting the task complete.
- **Follow best practices.** Idiomatic FastAPI, Pydantic v2 syntax, modern SQLAlchemy 2.0 style, PEP 8 naming. If unsure, match the convention already in the codebase.
- **Type hints everywhere.** Every function signature and Pydantic field is typed. `mypy`/`pyright` should pass.
- **Async by default for routes.** FastAPI endpoints are `async def` unless they call blocking code that can't be made async.
- **Separate models and schemas.** SQLAlchemy ORM classes go in `models/`; Pydantic classes go in `schemas/`. Never merge them.
- **Dependency injection via `Depends()`.** DB sessions, settings, agents, and auth all flow through FastAPI dependencies — no module-level singletons passed around.
- **Log, don't print.** Use `logging.getLogger(__name__)`. `print()` is for scratch only and must not land in committed code.
- **Config comes from env.** All environment-dependent values go through `app.core.config.settings` — no hardcoded URLs, keys, or paths.
- **Validate at boundaries.** Pydantic handles input validation at the route layer; internal functions trust their callers and don't re-validate.
- **Ask before adding dependencies.** Check if the stdlib or existing deps already solve it before adding to `pyproject.toml`. Use `uv add <pkg>` (not `pip install`) so the lockfile stays in sync.
- **Small, focused changes.** One concern per commit. Don't bundle refactors with feature work.
- **No comments for what the code says.** Only comment the *why* when it's non-obvious (a workaround, a constraint, a subtle invariant).
- **Never commit secrets.** `.env` stays gitignored; `.env.example` documents the shape.
- **Never load log files.** Do not read files from `backend/logs/` — they are runtime output and can be large. Diagnose issues from source code, tests, and structured logging configuration instead.

## Tech stack

### Backend (`backend/`)
- **FastAPI** — web framework, async routes, dependency injection
- **Pydantic v2** — request/response schemas and settings management (`BaseSettings`)
- **Pydantic-AI** — agent framework for structured LLM interactions
- **SQLAlchemy 2.0** — async ORM for persistence (engine/session wired in `app/databases/`)
- **asyncpg** — async PostgreSQL driver (Supabase)
- **Alembic** — database schema migration management (`backend/alembic/`)
- **Python stdlib `logging`** — configured in `app/core/logging.py`
- **uv** — package/dependency manager and virtual environment tool (replaces pip + venv)

### Frontend (`frontend/`)
- **React 18** — component-based UI
- **TypeScript** — typed frontend code
- **Vite** — dev server and build tool
- **Node / npm** — frontend dependency management

## Project structure

```
personal-finance-agent/
├── backend/
│   ├── alembic/                 # Alembic migration environment
│   │   ├── env.py               # Async migration runner (reads settings.database_url)
│   │   └── versions/            # Migration scripts (one per schema change)
│   ├── alembic.ini              # Alembic config (sqlalchemy.url injected from settings)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app instance, router includes, lifespan
│   │   ├── core/                # Cross-cutting infrastructure
│   │   │   ├── config.py        # Pydantic BaseSettings (env-driven); db_connect_args property
│   │   │   └── logging.py       # configure_logging() called on startup
│   │   ├── databases/           # SQLAlchemy engine + session factory
│   │   ├── dependencies/        # Shared Depends() factories (db session, agents)
│   │   ├── routes/              # APIRouter modules (one per resource/feature)
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── agents/              # Pydantic-AI agent definitions and tools
│   │   └── services/            # Business logic between routes and models/agents
│   ├── tests/                   # pytest suite (uses SQLite in-memory)
│   ├── logs/                    # Runtime log output (contents gitignored)
│   └── uploads/                 # User-uploaded files (contents gitignored)
├── frontend/
│   ├── src/
│   │   ├── api/                 # Typed API client functions
│   │   ├── components/          # Shared React components
│   │   ├── pages/               # Page-level components
│   │   ├── types/               # TypeScript type definitions
│   │   └── utils/               # Frontend utilities
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── .env                         # Local secrets (gitignored)
├── .env.example                 # Documents required env vars
├── pyproject.toml               # Python project config and pytest settings
└── uv.lock
```

## Running the app

```bash
# From the project root — activate venv once
source .venv/bin/activate

# Start the backend (run from backend/)
cd backend
uv run python -m app.main
# or: uv run uvicorn app.main:app --reload

# Start the frontend dev server (run from frontend/)
cd frontend
npm install   # first time only
npm run dev
```

Backend: `http://127.0.0.1:8000` · Frontend dev server: `http://localhost:5173`

## Conventions

- `models/` holds SQLAlchemy classes; `schemas/` holds Pydantic classes — keep them separate.
- `databases/` holds the SQLAlchemy engine and session factory; `dependencies/` holds `Depends()` factories.
- Settings are accessed via a single `settings` instance imported from `app.core.config`.
- Logging is configured once at app startup; modules call `logging.getLogger(__name__)`.
- `backend/logs/` and `backend/uploads/` are tracked in git via `.gitkeep` but their contents are gitignored.
- All file-system paths inside the package use `Path(__file__).resolve().parents[N]` — never CWD-relative strings.
- `import app.*` (not `backend.app.*`) — the package root is `backend/`, added to `sys.path` by `pyproject.toml` for tests and by the CWD when running from `backend/`.
- **Schema migrations via Alembic.** Run `alembic upgrade head` from `backend/` before starting the app against a new database. Generate new migrations with `alembic revision --autogenerate -m "description"` after changing models.
- **Tests use SQLite in-memory.** The pytest suite sets `DATABASE_URL=sqlite+aiosqlite:///:memory:` per-fixture and does not require a live PostgreSQL connection.
