# Agent Webapp Template

A template for building server-rendered web applications with a [Pydantic AI](https://ai.pydantic.dev/) agent backend.

## Stack

- **FastAPI** — async web framework with dependency injection
- **Pydantic AI** — structured LLM agent framework
- **Pydantic v2** — request/response schemas and settings via `BaseSettings`
- **SQLAlchemy 2.0** — async ORM
- **Jinja2** — server-side HTML templating
- **uv** — dependency and virtual environment management

## Getting started

### 1. Clone and install dependencies

```bash
git clone https://github.com/tascoma/agent-webapp-template.git
cd agent-webapp-template
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in the values in `.env`:

```env
APP_ENV=development
SECRET_KEY=changeme
DATABASE_URL=sqlite+aiosqlite:///./app.db
ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Run the dev server

```bash
uv run uvicorn app.main:app --reload
```

## Project structure

```
agent-webapp-template/
├── app/
│   ├── main.py              # FastAPI app instance, router includes, lifespan
│   ├── core/
│   │   ├── config.py        # Pydantic BaseSettings (env-driven)
│   │   └── logging.py       # Logging configuration
│   ├── databases/           # SQLAlchemy engine and session factory
│   ├── dependencies/        # Shared Depends() factories
│   ├── routes/              # APIRouter modules (one per resource)
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── agents/              # Pydantic AI agent definitions
│   ├── services/            # Business logic layer
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── tests/
├── logs/
└── uploads/
```

## Using this template

See [CLAUDE.md](CLAUDE.md) for step-by-step wiring instructions covering each layer of the stack.
