"""Long-running PostgreSQL worker for autonomous prediction reinforcement."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

from alert_tracker import EvidenceUnchanged, progressive_predict
from history_store import save_snapshot
from monitoring_store import (
    WORKER_ID,
    cancel_jobs_outside_targets,
    claim_due_job,
    create_alert_level_event,
    ensure_monitoring_job,
    fail_job,
    monitoring_job_is_running,
    normalize_hourly_schedule,
    record_environmental_evidence,
    recover_stale_jobs,
    reschedule_job,
)
from alert_store import heartbeat
from history_store import _postgres_connection
from coverage_store import list_active_forecast_cells
from firebase_auth import retry_one_firebase_cleanup
from evidence_store import persist_and_link_evidence, records_from_prediction
from outcome_store import collect_recent_outcomes
from prediction_cache import MODEL_VERSION
from validation_service import run_stored_validation
from central_outlooks import central_target_dates

POLL_SECONDS = max(5, int(os.getenv("WORKER_POLL_SECONDS", "30")))
WORKER_CONCURRENCY = max(1, min(8, int(os.getenv("WORKER_CONCURRENCY", "3"))))


def seed_central_jobs() -> None:
    """Ensure two validated daily outlook targets per shared forecast cell.

    Each target is an independent application of the validated daily binary
    classifier to that calendar day's 72-hour input window. Day+2 is not
    scheduled until the multi-horizon model completes evaluation.
    """
    today = datetime.now(timezone.utc).date()
    targets = set(central_target_dates(today))
    cells = list_active_forecast_cells()
    locations = [(float(cell["lat"]), float(cell["lon"]), cell["name"]) for cell in cells]
    for lat, lon, _ in locations:
        cancel_jobs_outside_targets(lat, lon, targets)
        for target in sorted(targets):
            ensure_monitoring_job(lat, lon, target)


async def process_job(job: dict) -> None:
    started = time.monotonic()
    target = datetime.combine(job["target_date"], datetime.min.time(), tzinfo=timezone.utc)
    result = await progressive_predict(float(job["lat"]), float(job["lon"]), target)
    if not monitoring_job_is_running(str(job["id"])):
        print(
            f"Discarded superseded central prediction job={job['id']} "
            f"target={job['target_date']}",
            flush=True,
        )
        return
    updates = result.get("history", [])
    previous_level = updates[-2]["alert_level"] if len(updates) >= 2 else None
    snapshot = save_snapshot({
        "lat": result["lat"], "lon": result["lon"],
        "location_name": result["location_name"], "target_date": result["target_date"],
        "recorded_at": result["prediction_time"], "probability": result["probability"],
        "alert_level": result["alert_level"], "dust_event": result["dust_event"],
        "data_source": "background-progressive-open-meteo+gee",
        "revision_reason": (
            "initial_central_prediction"
            if not updates[:-1]
            else "new_environmental_evidence"
        ),
        "evidence_fingerprint": result["evidence_fingerprint"],
        "observed_fraction": result["data_composition"]["observed_fraction"],
        "forecast_fraction": result["data_composition"]["forecast_fraction"],
        "input_completeness": result["data_composition"]["input_completeness"],
        "metadata": {
            "worker_id": WORKER_ID, "monitoring_job_id": str(job["id"]),
            "trend": result["trend"], "revision": result["update_count"],
            "surface_data": result["surface_data"],
            "input_quality": result["input_quality"],
        },
    })
    persist_and_link_evidence(
        snapshot["id"],
        result["lat"],
        result["lon"],
        result["location_name"],
        records_from_prediction(result),
    )
    # Retain the legacy wide observation table while deployed clients migrate
    # to field-level evidence returned by the latest-prediction endpoint.
    record_environmental_evidence(result)
    create_alert_level_event(job["tracking_key"], snapshot["id"], previous_level, result)
    reschedule_job(str(job["id"]), snapshot["id"], job["target_date"])
    print(
        f"Central prediction stored location={result['location_name']!r} "
        f"target={result['target_date']} snapshot={snapshot['id']} "
        f"probability={result['probability']:.4f} "
        f"duration_seconds={time.monotonic() - started:.2f}",
        flush=True,
    )


async def process_claimed_job(job: dict) -> None:
    """Finish one claimed job without terminating the long-running worker."""
    try:
        await process_job(job)
    except EvidenceUnchanged:
        snapshot_id = job.get("last_snapshot_id")
        if snapshot_id:
            reschedule_job(str(job["id"]), str(snapshot_id), job["target_date"])
        else:
            fail_job(str(job["id"]), EvidenceUnchanged("No prior revision is available"))
        print(
            f"Central prediction unchanged job={job['id']} target={job['target_date']}",
            flush=True,
        )
    except Exception as exc:
        fail_job(str(job["id"]), exc)
        print(f"Job {job['id']} failed: {type(exc).__name__}: {exc}", flush=True)


async def run_forever() -> None:
    print(
        f"SahelWatch reinforcement worker started: {WORKER_ID} "
        f"concurrency={WORKER_CONCURRENCY}",
        flush=True,
    )
    last_seed = None
    active: set[asyncio.Task[None]] = set()
    while True:
        try:
            today = datetime.now(timezone.utc).date()
            if last_seed != today:
                recover_stale_jobs()
                seed_central_jobs()
                outcome_result = await collect_recent_outcomes()
                print(
                    "MODIS outcome collection "
                    f"checked={outcome_result['checked']} "
                    f"stored={outcome_result['stored']}",
                    flush=True,
                )
                if outcome_result["stored"]:
                    validation = run_stored_validation(MODEL_VERSION)
                    print(
                        "Leakage-safe validation completed "
                        f"run={validation['validation_run_id']} "
                        f"cases={validation['overall']['count']}",
                        flush=True,
                    )
                normalized = normalize_hourly_schedule()
                if normalized:
                    print(
                        f"Moved {normalized} central jobs to the next hourly run",
                        flush=True,
                    )
                with _postgres_connection() as connection:
                    connection.execute("SELECT purge_sahelwatch_expired_data()")
                last_seed = today
            heartbeat("reinforcement", WORKER_ID, "running")
            # Account removal must not depend on the optional SMS worker being
            # deployed. Process one due seven-day Firebase cleanup per cycle.
            retry_one_firebase_cleanup()
            while len(active) < WORKER_CONCURRENCY:
                job = claim_due_job()
                if not job:
                    break
                active.add(asyncio.create_task(process_claimed_job(job)))
            if not active:
                await asyncio.sleep(POLL_SECONDS)
                continue
            completed, _ = await asyncio.wait(
                active, timeout=POLL_SECONDS, return_when=asyncio.FIRST_COMPLETED
            )
            active.difference_update(completed)
            for task in completed:
                task.result()
        except Exception as exc:
            print(f"Worker loop error: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
