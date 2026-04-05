#!/usr/bin/env bash
# One-shot data-check stuck-run sweep (for cron / make sweep-data-check).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"
PY=$(api_python)
exec "$PY" "$REPO_ROOT/scripts/sweep_data_check_stuck.py"
