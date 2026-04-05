#!/usr/bin/env python3
"""
One-shot data-check stuck-run sweep for cron or systemd timers.

Runs the same ``sweep_stuck_runs`` logic as the idle path inside
``scripts/job_worker.py`` (SLA terminalization, stale check recovery,
first-wave re-enqueue, follow-ups). Use when:

- the job queue stays busy for long stretches (few idle windows), or
- you want recovery independent of the long-running worker process.

Environment: same DB and Redis settings as the API/worker (load ``.env`` before
running in production).

Usage::

  PYTHONPATH=apps/api/src python scripts/sweep_data_check_stuck.py

Cron example (every 5 minutes)::

  */5 * * * * cd /path/to/inVision && . .venv/bin/activate && \\
    set -a && [ -f .env ] && . ./.env && set +a && \\
    PYTHONPATH=apps/api/src python scripts/sweep_data_check_stuck.py >> /var/log/invision-sweep.log 2>&1

Exit status: 0 on success (including recovered=0), 1 on fatal error.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from invision_api.db.session import SessionLocal
from invision_api.services.data_check.orchestrator_service import sweep_stuck_runs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [sweep_data_check] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        db = SessionLocal()
    except Exception:
        logger.exception("session_open_failed")
        return 1
    try:
        n = sweep_stuck_runs(db)
        db.commit()
        if n:
            logger.info("sweep_done recovered=%d", n)
        else:
            logger.info("sweep_done recovered=0")
        return 0
    except Exception:
        db.rollback()
        logger.exception("sweep_error")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
