#!/usr/bin/env bash
# Run Alembic migrations against DATABASE_URL from .env.
# Run this in every environment (local, staging, production) after pulling API changes that add or alter
# tables/columns; ORM models that map columns not yet in the database will fail at query time.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"
cd "$REPO_ROOT/apps/api"
PY=$(api_python)
exec "$PY" -m alembic upgrade head
