# CLAUDE.md

Practice project for building a server-rendered web app with an AI agent backend.

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
- **Never load log files.** Do not read files from `logs/` — they are runtime output and can be large. Diagnose issues from source code, tests, and structured logging configuration instead.

## Tech stack

- **FastAPI** — web framework, async routes, dependency injection
- **Pydantic v2** — request/response schemas and settings management (`BaseSettings`)
- **Pydantic-AI** — agent framework for structured LLM interactions
- **Jinja2** — server-side HTML templating (via `fastapi.templating.Jinja2Templates`)
- **SQLAlchemy** — ORM for persistence (engine/session wired in `app/databases/`)
- **Python stdlib `logging`** — configured in `app/core/logging.py`
- **uv** — package/dependency manager and virtual environment tool (replaces pip + venv)

## Project scaffold

```
agent-webapp-template/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app instance, router includes, lifespan
│   ├── core/                # Cross-cutting infrastructure
│   │   ├── config.py        # Pydantic BaseSettings (env-driven)
│   │   └── logging.py       # configure_logging() called on startup
│   ├── databases/           # SQLAlchemy engine + session factory
│   ├── dependencies/        # Shared Depends() factories (db session, current user, agents)
│   ├── routes/              # APIRouter modules (one per resource/feature)
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── agents/              # Pydantic-AI agent definitions and tools
│   ├── services/            # Business logic between routes and models/agents
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images served at /static
├── tests/                   # pytest suite
├── logs/                    # Runtime log output (contents gitignored)
└── uploads/                 # User-uploaded files (contents gitignored)
```

## Wiring up a new application

Follow these steps in order when starting a new feature or standing up the app for the first time.

### 0. Virtual environment
Create the virtualenv and install all dependencies before touching any code:

```bash
uv venv
uv sync
```

`uv venv` creates `.venv/` in the project root. `uv sync` installs every dependency declared in `pyproject.toml` (including dev extras). Run `uv add <pkg>` to add new packages — never `pip install`.

### 1. Environment
Copy `.env.example` to `.env` and fill in real values. Add any new env vars to both files — `.env.example` documents the shape, `.env` holds the secrets (gitignored).

### 2. Settings (`app/core/config.py`)
Define a `Settings` class using `pydantic_settings.BaseSettings`. Declare every env var the app needs as a typed field. Expose a single module-level `settings` instance. All other modules import from here — never read `os.environ` directly.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str
    database_url: str
    anthropic_api_key: str
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_file": ".env"}

settings = Settings()
```

### 3. Logging (`app/core/logging.py`)
Implement a `configure_logging()` function that sets the root log level and format. Call it once from the lifespan in `main.py`. Every other module gets its logger via `logging.getLogger(__name__)`.

### 4. Database (`app/databases/`)
Create the async SQLAlchemy engine and `AsyncSessionLocal` factory using `DATABASE_URL` from `settings`. Export a `get_db` async generator that yields a session — this becomes a `Depends()` target.

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### 5. Models (`app/models/`)
One file per resource (e.g. `user.py`). Inherit from a shared `Base = DeclarativeBase()` defined in `app/databases/`. Use SQLAlchemy 2.0 mapped-column style with full type annotations.

### 6. Schemas (`app/schemas/`)
One file per resource. Define separate `Create`, `Update`, and `Read` Pydantic models. `Read` schemas include the database-generated fields (e.g. `id`, `created_at`). Never share a class between ORM and Pydantic layers.

### 7. Dependencies (`app/dependencies/`)
Collect all reusable `Depends()` factories here — db session, `current_user`, agent instances, pagination params, etc. Import `get_db` from `app.databases` and compose upward.

### 8. Agents (`app/agents/`)
Define each Pydantic-AI agent in its own file. Wire API keys from `settings`. Expose agents through a dependency factory in `app/dependencies/` so routes receive them via `Depends()` and tests can swap them.

**Agent design rule:** deterministic logic must not be delegated to the LLM. If a step can be expressed as plain Python (parsing, filtering, math, lookups, conditionals), implement it as a regular function and call it from a tool or service. Only use the LLM for steps that genuinely require language understanding, inference, or judgment. Keep agent tools thin — they should validate inputs, call a plain function, and return a structured result.

### 9. Services (`app/services/`)
One file per resource or use-case. Services accept a db session and/or agent as arguments (injected by the route via `Depends()`). They own the business logic — routes stay thin.

### 10. Routes (`app/routes/`)
One `APIRouter` per resource. Mount each router in `main.py` with a prefix and tags. Return Pydantic schema instances or `TemplateResponse` — never raw dicts or ORM objects directly. Each resource router should expose the full CRUD operations (create, read list, read one, update, delete) — omit an endpoint only when the resource genuinely doesn't support that operation.

### 11. Templates & static (`app/templates/`, `app/static/`)
Mount `Jinja2Templates` and `StaticFiles` in `main.py`. Keep templates organized in subdirectories by feature. Reference static assets via the `/static` URL prefix.

### 12. Main (`app/main.py`)
Wire everything together here:
- Create the `FastAPI` instance.
- Define a `lifespan` context manager: call `configure_logging()`, run `async_engine.dispose()` on shutdown.
- Include all routers.
- Mount `StaticFiles`.

Include an entry point so the app can be run with `python3 -m app.main`:

```python
if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_excludes=["logs/*"],
    )
```

### 13. Tests (`tests/`)
Use `httpx.AsyncClient` with `ASGITransport` against the real app. Use a separate test database (override the `get_db` dependency). One test file per route module.

## Conventions

- `models/` holds SQLAlchemy classes; `schemas/` holds Pydantic classes — keep them separate.
- `databases/` holds the SQLAlchemy engine and session factory; `dependencies/` holds `Depends()` factories.
- Settings are accessed via a single `settings` instance imported from `app.core.config`.
- Logging is configured once at app startup; modules call `logging.getLogger(__name__)`.
- Templates and static assets live inside `app/` so they ship with the package.
- `logs/` and `uploads/` are tracked in git via `.gitkeep` but their contents are gitignored.
