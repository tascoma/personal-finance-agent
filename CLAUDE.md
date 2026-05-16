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
- **python-jose** — JWT encoding/decoding for access and refresh tokens
- **bcrypt** — password hashing
- **Python stdlib `logging`** — configured in `app/core/logging.py`
- **uv** — package/dependency manager and virtual environment tool (replaces pip + venv)

### Frontend (`frontend/`)
- **React 18** — component-based UI
- **TypeScript** — typed frontend code
- **Vite** — dev server and build tool
- **Node / npm** — frontend dependency management

## Platforms

External services this app depends on:

- **GitHub** (`tascoma/personal-finance-ai`) — source of truth. Pushes to `main` deploy to the prod Render service; pushes to `dev` deploy to the staging Render service.
- **Render** — hosts two web services in region `oregon`, both built from the multi-stage Dockerfile. Each service has its own `DATABASE_URL` pointing at a different Supabase project (see below):
  - **Production** — `personal-finance-ai` (`srv-d7vngnlckfvc73eq4uq0`), tracks `main`, served at https://personal-finance-agent-ipuu.onrender.com (URL pre-dates the rename; Render hostnames don't change on rename). Connects to the Supabase prod project.
  - **Staging** — `personal-finance-ai-stage` (`srv-d81rnpfaqgkc73ctsad0`), tracks `dev`, served at https://personal-finance-agent-1-tqet.onrender.com. Connects to the Supabase `stage` branch.
- **Supabase** — managed PostgreSQL accessed via `asyncpg`. Schema is owned by Alembic — never edit tables in the Supabase UI. Two databases are wired up via Pro-plan branching, and each `DATABASE_URL` is the transaction-pooler URI on port 6543 (`aws-1-us-west-2.pooler.supabase.com`):
  - **Prod** — project ref `bupibumcqijqpsqisslg` (the persistent main branch). The Render prod service and local `.env` both point here. **Local dev currently writes to prod data — treat the local `.env` accordingly until we wire it to stage.**
  - **Stage** — branch ref `fkolwbrvxvmmcukkxvgy` (persistent, tied to git `dev`). Migrations run here first via the Render staging deploy; promote schema + features to prod by merging `dev` → `main`. The branch was bootstrapped empty (no prod data carryover); seed the chart of accounts and create a user via `backend/scripts/create_user.py` before using staging.
  - **Migration quirk to know about:** the `7fceefecdbfb_add_users_table` Alembic revision is a `pass` no-op even though `a3e1f2c8d501` ALTERs `users`. Prod's `users` table was created outside Alembic at some point. When bootstrapping a fresh database (e.g. a new branch), run `alembic upgrade 7fceefecdbfb`, manually `CREATE TABLE users` to match prod (without `token_version`), then `alembic upgrade head`. Don't retroactively edit the migration file without coordinating — prod's `alembic_version` is already at head.
- **Anthropic (Claude)** — LLM behind every Pydantic-AI agent in `app/agents/`. Requires `ANTHROPIC_API_KEY`. Default model is Claude Sonnet 4.6

Build-time package sources: **PyPI** (via `uv`), **npm registry**, **Docker Hub / GHCR** (`node:20-alpine`, `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`).

**Frontend lockfile gotcha:** Render's `node:20-alpine` ships **npm 10.8.2**. Lockfiles generated with newer npm omit `optional`/`os` metadata on platform-specific packages and break `npm ci` in the build. If you regenerate `frontend/package-lock.json`, do it with `npx -y npm@10.8.2 install`.

## Branching workflow

- **`main`** — production. Render auto-deploys from every push to `main`. Protected: changes only land via pull request.
- **`dev`** — long-lived integration branch. All day-to-day work happens here or on branches cut from it. Never delete.
- **Feature branches** — branched off `dev` (e.g. `feat/transaction-import`, `fix/auth-refresh`). Merge back into `dev` via PR (or fast-forward locally for trivial work).
- **Promotion to prod** — when `dev` is stable, open a PR from `dev` → `main`. Merging that PR triggers the Render deploy.

Day-to-day:

```bash
git checkout dev && git pull
git checkout -b feat/<short-name>      # do the work, commit
git push -u origin feat/<short-name>   # open PR into dev
# after merge:
git checkout dev && git pull           # delete the feature branch
```

## Project structure

```
personal-finance-ai/
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
│   │   ├── dependencies/        # Shared Depends() factories (db session, agents, get_current_user)
│   │   ├── routes/              # APIRouter modules (one per resource/feature)
│   │   ├── models/              # SQLAlchemy ORM models (including User)
│   │   ├── schemas/             # Pydantic request/response schemas (including auth schemas)
│   │   ├── agents/              # Pydantic-AI agents (each module = prompt + output schema)
│   │   │   └── _base.py         # Shared Agent factory + AgentError-wrapping run_agent()
│   │   └── services/            # Business logic between routes and models/agents
│   ├── scripts/                 # One-off operational/diagnostic scripts
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
- **Authentication.** JWT-based auth with short-lived access tokens (Bearer) and long-lived refresh tokens (HttpOnly cookie, scoped to `/api/v1/auth`). Use the `get_current_user` dependency from `app.dependencies` to protect any route. The `services/auth.py` layer handles hashing, JWT creation/decoding, and DB lookups; the route layer only maps `AuthError` → HTTP status codes. The `SECRET_KEY` env var must be set to a non-default value in production.
- **Agents.** Each agent module under `app/agents/` defines only its prompt and output Pydantic model, then calls `build_agent` / `run_agent` from `_base.py`. Failures inside `run_agent` are wrapped as `AgentError` — route handlers catch `AgentError` (not bare `Exception`) and return a generic 502 so internal exception strings never leak to clients.
- **Request IDs and logging.** `RequestIdMiddleware` reads the `x-request-id` header (or mints one) per request, stores it in a `ContextVar`, and echoes it back in the response. The log format is `%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s`, so any log line emitted during a request is correlatable with the client's request id.
