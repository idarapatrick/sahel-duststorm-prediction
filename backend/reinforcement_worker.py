"""Long-running PostgreSQL worker for autonomous prediction reinforcement."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from alert_tracker import progressive_predict
from history_store import save_snapshot
from monitoring_store import (
    WORKER_ID,
    claim_due_job,
    create_alert_level_event,
    ensure_monitoring_job,
    fail_job,
    record_environmental_evidence,
    recover_stale_jobs,
    reschedule_job,
)
from alert_store import heartbeat
from history_store import _postgres_connection

POLL_SECONDS = max(5, int(os.getenv("WORKER_POLL_SECONDS", "30")))

CENTRAL_LOCATIONS = [
    (13.51, 2.11, "Niamey, Niger"),
    (13.06, 5.24, "Sokoto, Nigeria"),
    (12.00, 8.52, "Kano, Nigeria"),
    (11.85, 13.16, "Maiduguri, Nigeria"),
    (16.97, 7.99, "Agadez, Niger"),
    (12.13, 15.06, "N'Djamena, Chad"),
    (12.64, -8.00, "Bamako, Mali"),
    (16.77, -3.01, "Timbuktu, Mali"),
    (12.36, -1.48, "Ouagadougou, Burkina Faso"),
    (14.69, -17.44, "Dakar, Senegal"),
    (18.09, -15.98, "Nouakchott, Mauritania"),
]


def seed_central_jobs() -> None:
    """Ensure tomorrow is monitored for every centrally covered location."""
    target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    for lat, lon, _ in CENTRAL_LOCATIONS:
        ensure_monitoring_job(lat, lon, target)


async def process_job(job: dict) -> None:
    target = datetime.combine(job["target_date"], datetime.min.time(), tzinfo=timezone.utc)
    result = await progressive_predict(float(job["lat"]), float(job["lon"]), target)
    updates = result.get("history", [])
    previous_level = updates[-2]["alert_level"] if len(updates) >= 2 else None
    snapshot = save_snapshot({
        "lat": result["lat"], "lon": result["lon"],
        "location_name": result["location_name"], "target_date": result["target_date"],
        "recorded_at": result["prediction_time"], "probability": result["probability"],
        "alert_level": result["alert_level"], "dust_event": result["dust_event"],
        "data_source": "background-progressive-open-meteo+gee",
        "metadata": {
            "worker_id": WORKER_ID, "monitoring_job_id": str(job["id"]),
            "confidence": result["data_composition"]["confidence_pct"],
            "trend": result["trend"], "revision": result["update_count"],
            "surface_data": result["surface_data"],
            "input_quality": result["input_quality"],
        },
    })
    record_environmental_evidence(result)
    create_alert_level_event(job["tracking_key"], snapshot["id"], previous_level, result)
    reschedule_job(str(job["id"]), snapshot["id"], job["target_date"])


async def run_forever() -> None:
    print(f"SahelWatch reinforcement worker started: {WORKER_ID}")
    last_seed = None
    while True:
        try:
            today = datetime.now(timezone.utc).date()
            if last_seed != today:
                recover_stale_jobs()
                seed_central_jobs()
                with _postgres_connection() as connection:
                    connection.execute("SELECT purge_sahelwatch_expired_data()")
                last_seed = today
            heartbeat("reinforcement", WORKER_ID, "running")
            job = claim_due_job()
            if not job:
                await asyncio.sleep(POLL_SECONDS)
                continue
            try:
                await process_job(job)
            except Exception as exc:
                fail_job(str(job["id"]), exc)
                print(f"Job {job['id']} failed: {type(exc).__name__}: {exc}")
        except Exception as exc:
            print(f"Worker loop error: {type(exc).__name__}: {exc}")
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
