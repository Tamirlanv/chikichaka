# Data check pipeline (Проверка данных)

This document fixes the end-to-end map and invariants for the data-check stage. It complements code in `apps/api/src/invision_api/services/data_check/` and the commission kanban hints.

## Two parallel job chains on submit

`application_service.submit_application_with_outcome` enqueues **both**:

- **Legacy / screening track:** `initial_screening_service.enqueue_post_submit_jobs` → Redis jobs `extract_text` (per document) and `initial_screening` (runs `run_screening_checks_and_record` in the worker). Order relative to data-check jobs is **not fixed** (queue scheduling).
- **Data-check track:** `submit_bootstrap_service.bootstrap_data_check_pipeline` → `data_check_unit` jobs for the nine policy units (waves + dependencies).

Operators should treat these as **independent** pipelines that share the same worker process and DB; diagnostics must look at **both** job types in logs.

## Flow (submit → queue → worker → aggregate → UI)

1. **Submit / bootstrap** — `submit_bootstrap_service.bootstrap_data_check_pipeline` creates a `CandidateValidationRun` and one `CandidateValidationCheck` per `DataCheckUnitType`, then enqueues first-wave jobs via `orchestrator_service.enqueue_first_wave_jobs`.
2. **Queue** — `job_dispatcher_service.enqueue_data_check_unit_job` pushes Redis payloads with `job_type=data_check_unit`, `application_id`, `run_id`, `unit_type`, `analysis_job_id`.
3. **Worker** — `scripts/job_worker.py` BRPOP loop; on idle, runs `sweep_stuck_runs` (and other sweeps). Each job is handled by `workers/job_worker.process_payload` → `job_runner_service.run_unit`.
4. **Unit execution** — `run_unit` recomputes aggregate from checks (not raw `run.overall_status`) to decide whether work is allowed, runs the processor from `job_registry.REGISTRY`, updates check + run, refreshes commission projection, enqueues follow-ups via `enqueue_ready_followup_jobs`.
5. **Aggregate** — `status_service.compute_run_status` over **all** `UNIT_POLICIES` units (missing checks count as `pending`). Until every policy unit is in a terminal unit status, the run stays `pending` or `running`. Terminal run outcomes: `failed`, `partial`, `ready`.
6. **UI** — Kanban border / data-check column uses recomputed status: `kanban_border_hints.latest_data_check_run_status` → `data_readiness.get_data_check_overall_status` (same recompute as checks). Personal info `processingStatus.overall` uses `personal_info_service._build_processing_status`, which also calls `compute_run_status` on the canonical policy map. **Invariant:** for the same application, `get_data_check_overall_status` and `processingStatus["overall"]` match when all policy checks exist.

## Invariants checklist

- [ ] Every in-flight run has checks covering each `UNIT_POLICIES` unit (bootstrap creates all rows).
- [ ] `CandidateValidationRun.overall_status` is one of `DataCheckRunStatus` values; legacy `processing` is normalized to `pending` (migration + code paths treat legacy rows as non-terminal).
- [ ] Sweep / SLA queries include non-terminal runs: `pending`, `running`, and legacy `processing` until DB is clean.
- [ ] Worker idle loop invokes data-check sweep so stuck `queued` / `pending` units are re-enqueued or failed.
- [ ] `UPLOAD_ROOT` is consistent between API and worker processes when validating files. The worker logs the resolved path at startup (`scripts/job_worker.py`: `Worker resolved UPLOAD_ROOT=...`).

## Smoke (manual or staging)

Run with API + Redis + worker + DB.

| Scenario | Expectation |
|----------|-------------|
| **Happy** | Submit → all units complete → run `ready` → kanban green border path; optional auto-advance per product rules. |
| **Mixed / partial** | Some units `failed` or `manual_review_required` → run `failed` or `partial` → orange border; application stays on `initial_screening` until commission acts. |
| **SLA** | Stop worker or block units past `DATA_CHECK_RUN_SLA_MINUTES` from `created_at` → idle sweep terminalizes non-terminal units → run leaves `pending`/`running`; logs include `sla_terminalize`. |

**API consistency:** For one `application_id`, compare `GET` personal info `processingStatus.overall` (or equivalent) with kanban/projection data-check status derived from `get_data_check_overall_status` — they should agree.

### Automated smoke (pytest)

From the API package root:

```bash
pytest tests/test_data_check_end_to_end_ready_state.py \
  tests/test_data_check_legacy_processing.py \
  tests/test_upload_root_and_processing_status.py::test_processing_status_overall_matches_kanban_aggregate \
  tests/test_commission_pipeline_readiness.py \
  -q
```

Covers happy-path pipeline, sweep/SLA paths, legacy `processing` visibility, and `processingStatus.overall` vs kanban aggregate alignment.

## Optional phase B

A single orchestration module (`schedule_wave`, `on_unit_complete`, `sweep`, …) is only justified if an audit shows duplicated logic or product needs explicit lifecycle APIs. Not required for correctness if the invariants above hold.
