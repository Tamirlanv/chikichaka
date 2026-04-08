#!/usr/bin/env bash
# One-shot derived-data backfill runner.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"
PY=$(api_python)
exec "$PY" "$REPO_ROOT/scripts/backfill_derived_applications.py" "$@"
