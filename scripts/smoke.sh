#!/usr/bin/env bash
# Run automated checks: API unit tests + web unit tests (Vitest).
# For manual HTTP checks with a running backend: curl -sf http://localhost:8000/api/v1/health
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== API (pytest) =="
cd "$ROOT/apps/api"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
export PYTHONPATH=src
pytest tests/ -q "$@"

echo "== Web (vitest) =="
cd "$ROOT/apps/web"
if command -v pnpm >/dev/null 2>&1; then
  pnpm test
else
  npx vitest run
fi

echo "Smoke tests OK."
