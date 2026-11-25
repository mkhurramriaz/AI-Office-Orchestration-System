# TaskFlow AI — Backend Engine

FastAPI asynchronous backend for TaskFlow AI, an AI-powered office task management and workflow orchestration platform.

---

## 1. Architecture Overview

The backend uses clean architecture with strict separation of concerns:

```
backend/
├── alembic/                # Database migrations (async SQLAlchemy support)
│   ├── env.py
│   └── versions/
├── alembic.ini             # Alembic configuration
├── app/
│   ├── api/                # HTTP presentation layer (FastAPI routers & endpoints)
│   │   ├── deps.py         # Dependency injection providers (DB session, auth)
│   │   └── v1/             # API version 1 namespace
│   │       ├── endpoints/
│   │       │   └── health.py # Health diagnostics and database ping
│   │       └── router.py   # Aggregated API router
│   ├── core/               # Centralized configuration & security
│   │   └── config.py       # Pydantic v2 BaseSettings loading from root .env
│   ├── database/           # Asynchronous persistence layer
│   │   ├── base.py         # DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│   │   └── session.py      # AsyncEngine, async_sessionmaker, get_db dependency
│   ├── agents/             # [Phase 4] LangGraph workflow nodes and state graphs
│   ├── models/             # [Phase 2] SQLAlchemy ORM data models
│   ├── schemas/            # [Phase 2] Pydantic DTOs and validation models
│   ├── services/           # [Phase 2-3] Business logic and RAG retriever services
│   ├── tools/              # [Phase 3-4] Agent tools for database & document queries
│   └── main.py             # FastAPI app factory, CORS, exception handlers, lifespan
├── pytest.ini              # Pytest configuration with asyncio support
├── requirements.txt        # Production-pinned Python 3.12 dependencies
└── tests/                  # Automated unit and integration test suite
```

---

## 2. Prerequisites

* **Python 3.12.10** (located in `backend/.venv`)
* **PostgreSQL 14+** (configured via environment variables)

> **Important:** Do not execute backend scripts using the repository root `.venv`, which runs experimental Python 3.14. Always use `backend/.venv`.

---

## 3. Environment Setup & Activation

### Windows (PowerShell):
```powershell
# Navigate to backend directory
cd backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Verify Python version (must report Python 3.12.10)
python --version
```

### Windows (Command Prompt):
```cmd
cd backend
.\.venv\Scripts\activate.bat
python --version
```

### Linux / macOS:
```bash
cd backend
source .venv/bin/activate
python --version
```

---

## 4. Dependency Installation

To install all verified dependencies:
```powershell
pip install -r requirements.txt
```

---

## 5. Configuration (.env)

The backend loads configuration from the repository root `.env` file via `pydantic-settings`. 

A configuration blueprint is provided in the repository root at `.env.example`:

```bash
# Copy template to .env if not already present
cp ../.env.example ../.env
```

Key environment settings:
* `DATABASE_URL`: Asynchronous PostgreSQL connection string (`postgresql+asyncpg://user:password@localhost:5432/taskflow_ai`).
* `DATABASE_URL_SYNC`: Synchronous PostgreSQL connection string for Alembic (`postgresql://user:password@localhost:5432/taskflow_ai`).
* `SECRET_KEY`: Secret key for JWT generation.
* `BACKEND_CORS_ORIGINS`: JSON array or comma-separated list of permitted origins.
* `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY`: Model provider keys.

---

## 6. Running the Development Server

Start the FastAPI application using Uvicorn:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
* **Interactive OpenAPI Docs:** [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)
* **OpenAPI JSON Spec:** [http://127.0.0.1:8000/api/v1/openapi.json](http://127.0.0.1:8000/api/v1/openapi.json)
* **Top-Level Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* **API v1 Health Check:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 7. Database Migrations (Alembic)

Alembic is configured for asynchronous migrations linked to `app.database.base.Base.metadata`:

```powershell
# View current database revision
alembic current

# Generate a new migration revision
alembic revision --autogenerate -m "describe migration"

# Apply migrations to database
alembic upgrade head

# Rollback one migration revision
alembic downgrade -1
```

---

## 8. Running Automated Tests

Run the full test suite using `pytest`:

```powershell
pytest -v
```

All integration tests use an isolated in-memory SQLite async database (`sqlite+aiosqlite:///:memory:`) to verify database queries, connection ping latency, health reports, CORS parsing, and error handling without mutating external databases.
