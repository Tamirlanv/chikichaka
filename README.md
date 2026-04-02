# inVision U — Admissions Platform

Monorepo: **Next.js (App Router)** candidate portal + **FastAPI** API + **PostgreSQL** + **Redis**.

## Prerequisites

- Node 22 + [pnpm](https://pnpm.io) 9
- Python 3.12
- Docker (optional, recommended for Postgres/Redis)

## Environment

Copy [.env.example](.env.example) to `.env` at the repository root and set:

- `DATABASE_URL` — `postgresql+psycopg://USER:PASS@HOST:5432/DB` (use `postgresql+psycopg://` for this codebase)
- `SECRET_KEY` — at least 32 characters
- `REDIS_URL`
- `RESEND_API_KEY` — required for registration (verification email)
- `EMAIL_FROM` — sender address on a domain **verified in Resend** (e.g. `noreply@oku.com.kz`)
- `OPENAI_API_KEY` — optional; used only for future committee/assistive features (no autonomous admission decisions)

## Quick commands (Makefile + `scripts/`)

From the repository root:

| Command | Description |
|--------|-------------|
| `make help` | List all targets |
| `make install` | Install frontend (pnpm) + API venv + pip |
| `make install-frontend` | Only `pnpm install` |
| `make install-api` | Only Python venv + `requirements.txt` |
| `make infra` | `docker compose up -d postgres redis` |
| `make init-db` | Create `POSTGRES_USER` / DB on local Postgres if role is missing (see [Troubleshooting](#troubleshooting)) |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Seed roles + internal test questions |
| `make backend` | FastAPI dev server (port **8000**) |
| `make frontend` | Next.js dev (port **3000**) |
| `make worker` | Redis job worker (scaffold) |
| `make docker-up` | Full stack: `docker compose up --build` |
| `make docker-down` | `docker compose down` |

Same behavior via shell: `bash scripts/backend.sh`, `bash scripts/frontend.sh`, etc.

Typical local flow: `make install` → copy `.env` → `make infra` → `make migrate` → `make seed` → in two terminals: `make backend` and `make frontend`.

## Local development (manual steps)

### 1. Start Postgres & Redis

```bash
make infra
# or: docker compose up -d postgres redis
```

### 2. API

```bash
make install-api
make migrate
make seed
make backend
```

Health: `GET http://localhost:8000/api/v1/health`  
OpenAPI: `http://localhost:8000/api/docs`

### 3. Web

```bash
make install-frontend
make frontend
```

The Next.js dev server rewrites `/api/v1/*` to the FastAPI backend (`API_INTERNAL_URL` or `http://127.0.0.1:8000`) so **httpOnly cookies** work on `localhost:3000`.

### 4. Job worker (optional)

```bash
make worker
```

## Full stack with Docker

```bash
cp .env.example .env
# Fill SECRET_KEY, RESEND_API_KEY, etc.
docker compose build
docker compose run --rm api sh -c "cd /app/apps/api && alembic upgrade head && cd /app && PYTHONPATH=apps/api/src python scripts/seed.py"
docker compose up
```

- API: `http://localhost:8000`
- Web: `http://localhost:3000`
- Uploads persist in the `upload_data` volume (API path `/data/uploads` inside the container).

## Production API (Railway / Docker)

The API image ([`infra/docker/Dockerfile.api`](infra/docker/Dockerfile.api)) runs, on each container start:

1. `alembic upgrade head`
2. [`scripts/seed_internal_test_questions.py`](scripts/seed_internal_test_questions.py) — idempotently ensures **40** active personality (`internal_test`) questions in PostgreSQL (same data as `seed_questions()` in [`scripts/seed.py`](scripts/seed.py)).
3. `uvicorn …`

So a fresh production database receives the question bank without a separate manual `make seed`, as long as the API process starts with a valid `DATABASE_URL`.

**Manual recovery** (e.g. if you deploy without this image or need to re-sync): from a shell with `DATABASE_URL` pointing at the target DB:

```bash
cd /path/to/inVision && PYTHONPATH=apps/api/src python scripts/seed_internal_test_questions.py
```

(or `make seed` for roles + questions + optional commission seed).

**Verify the internal test contract** (as an authenticated candidate):

- `GET /api/v1/internal-test/questions` should return a JSON array of length **40**, each item with `question_type` `single_choice` (or `multi_choice`), stable `id` values matching the frontend [`PERSONALITY_QUESTION_IDS`](apps/web/lib/personality-profile/questions.ts) pattern `00000000-0000-4000-8000-…`.
- If the list is empty or shorter than 40, logs will show a startup warning from the API (`expected 40 active questions, found N`).

## Troubleshooting

### `make infra` prints `infra is up to date` and does nothing

There is a real directory [`infra/`](infra/) in the repo (Dockerfiles). **GNU Make** treats the target name `infra` as that folder, so it skipped the recipe. The root [`Makefile`](Makefile) declares phony targets (including `infra`) so `make infra` always runs `docker compose up -d postgres redis`.

### `Cannot connect to the Docker daemon`

Start **Docker Desktop** (or your Docker engine), then run `make infra` again.

### Wrong Compose syntax

Use `docker compose up -d postgres redis` (or `make infra`), not `docker compose -d postgres …`.

### `FATAL: role "invision" does not exist` (during `make migrate`)

`DATABASE_URL` points to **localhost:5432**, but the server answering on that port is **not** the one that has the `invision` user (typical on macOS: **Homebrew PostgreSQL** is bound to 5432, while Docker Postgres never receives connections or uses a different data directory).

**Fix (pick one):**

1. **Use Docker Postgres only** — stop the local service so it releases 5432, then start the stack DB:
   ```bash
   # example: brew services stop postgresql@16   # adjust version
   make infra
   sleep 3
   make migrate
   ```
2. **Stay on local Postgres** — create the role and database to match `.env`:
   ```bash
   make init-db
   make migrate
   ```
   Or run the SQL yourself as a superuser: [scripts/sql/init_invision_role_and_db.sql](scripts/sql/init_invision_role_and_db.sql).

3. **Use another user** — set `DATABASE_URL` / `POSTGRES_*` in `.env` to a role that already exists on your server.

## Architecture notes

- **Auth**: JWT access + refresh cookies (`invision_access`, `invision_refresh`); refresh rotation with Redis-backed revocation list.
- **Applications**: One non-archived application per candidate (partial unique index). Sections stored as JSONB with Pydantic validation per section.
- **Internal test**: Question bank in PostgreSQL (seeded on API startup via Docker/Railway, or `make seed` locally); answers persisted; final submit locks answers and completes the section. Scoring keys in [`personality_profile_service.py`](apps/api/src/invision_api/services/personality_profile_service.py) must stay aligned with [`questions.ts`](apps/web/lib/personality-profile/questions.ts) (see API/web consistency tests).
- **Documents**: Local storage adapter under `UPLOAD_ROOT`; swap for S3-compatible storage later.
- **Committee / AI**: Schema includes `committee_reviews` and `ai_review_metadata`; AI helpers must not perform final admission decisions.

## Commands cheat sheet

| Task        | Command |
|------------|---------|
| Migrations | `make migrate` |
| Create local DB role (if missing) | `make init-db` |
| Seed roles/questions | `make seed` |
