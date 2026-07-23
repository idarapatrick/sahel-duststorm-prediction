"""PostgreSQL queue operations for background prediction reinforcement."""

from __future__ import annotations

import os
import socket
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from history_store import _postgres_connection, _using_postgres

WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
# SahelWatch's product contract is one central revision per forecast cell per
# UTC hour. This is deliberately not deployment-configurable: a stale Render
# value previously reduced the cadence to six hours without changing the UI.
MONITOR_INTERVAL_HOURS = 1
MONITOR_RETRY_MINUTES = max(1, int(os.getenv("MONITOR_RETRY_MINUTES", "15")))
MONITOR_MAX_ATTEMPTS = max(1, int(os.getenv("MONITOR_MAX_ATTEMPTS", "8")))


def tracking_key(lat: float, lon: float, target_date: date | str) -> str:
    return f"{lat:.3f}_{lon:.3f}_{target_date}"


def monitoring_window(target_date: date) -> tuple[datetime, datetime]:
    target = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    return target - timedelta(hours=60), target + timedelta(hours=12)


def ensure_monitoring_job(
    lat: float,
    lon: float,
    target_date: date,
    *,
    first_run_at: datetime | None = None,
) -> str | None:
    """Idempotently create one active job for a location and target date."""
    if not _using_postgres():
        return None
    key = tracking_key(lat, lon, target_date)
    window_start, window_end = monitoring_window(target_date)
    now = datetime.now(timezone.utc)
    if now > window_end:
        return None
    due = first_run_at or max(now, window_start)
    job_id = str(uuid.uuid4())
    with _postgres_connection() as connection:
        connection.execute(
            """INSERT INTO monitoring_jobs
               (id, tracking_key, lat, lon, target_date, status, next_run_at)
               VALUES (%s,%s,%s,%s,%s,'pending',%s)
               ON CONFLICT DO NOTHING""",
            (job_id, key, lat, lon, target_date, due),
        )
        row = connection.execute(
            """SELECT id FROM monitoring_jobs
               WHERE tracking_key=%s AND status IN ('pending','running','failed')
               ORDER BY created_at DESC LIMIT 1""",
            (key,),
        ).fetchone()
    return str(row["id"]) if row else None


def cancel_superseded_jobs(lat: float, lon: float, target_date: date) -> int:
    """Keep one central target active when the calendar day rolls forward."""
    if not _using_postgres():
        return 0
    with _postgres_connection() as connection:
        result = connection.execute(
            """UPDATE monitoring_jobs
               SET status='cancelled', completed_at=now(), locked_at=NULL,
                   locked_by=NULL, last_error='Superseded by the current central target',
                   updated_at=now()
               WHERE lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
                 AND target_date <> %s
                 AND status IN ('pending','running','failed')""",
            (lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001, target_date),
        )
        return result.rowcount


def recover_stale_jobs(lock_timeout_minutes: int = 30) -> int:
    if not _using_postgres():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lock_timeout_minutes)
    with _postgres_connection() as connection:
        result = connection.execute(
            """UPDATE monitoring_jobs SET status='failed', locked_at=NULL,
                      locked_by=NULL, next_run_at=now(),
                      last_error='Worker lock expired', updated_at=now()
               WHERE status='running' AND locked_at < %s""",
            (cutoff,),
        )
        return result.rowcount


def normalize_hourly_schedule() -> int:
    """Pull legacy six-hour jobs forward to the next UTC hour."""
    if not _using_postgres():
        return 0
    next_hour = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    with _postgres_connection() as connection:
        result = connection.execute(
            """UPDATE monitoring_jobs
               SET next_run_at=%s, updated_at=now()
               WHERE status IN ('pending','failed') AND next_run_at>%s""",
            (next_hour, next_hour),
        )
        return result.rowcount


def claim_due_job(worker_id: str = WORKER_ID) -> dict[str, Any] | None:
    """Atomically claim one due job; SKIP LOCKED permits multiple workers."""
    if not _using_postgres():
        raise RuntimeError("The reinforcement worker requires PostgreSQL")
    with _postgres_connection() as connection:
        row = connection.execute(
            """WITH due AS (
                 SELECT id FROM monitoring_jobs
                 WHERE status IN ('pending','failed') AND next_run_at <= now()
                   AND attempts < %s
                 ORDER BY next_run_at, created_at
                 FOR UPDATE SKIP LOCKED LIMIT 1
               )
               UPDATE monitoring_jobs j
               SET status='running', locked_at=now(), locked_by=%s,
                   attempts=j.attempts+1, updated_at=now()
               FROM due WHERE j.id=due.id RETURNING j.*""",
            (MONITOR_MAX_ATTEMPTS, worker_id),
        ).fetchone()
    return dict(row) if row else None


def monitoring_job_is_running(job_id: str) -> bool:
    """Confirm that a claimed job was not superseded during inference."""
    with _postgres_connection() as connection:
        row = connection.execute(
            "SELECT status FROM monitoring_jobs WHERE id=%s", (job_id,)
        ).fetchone()
    return bool(row and row["status"] == "running")


def prediction_schedule(lat: float, lon: float, target_date: date) -> dict[str, Any]:
    """Return the next central update and whether a worker currently owns it."""
    if not _using_postgres():
        return {"status": "unavailable", "next_update_at": None, "updating": False}
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT status,next_run_at,locked_at,updated_at
               FROM monitoring_jobs
               WHERE target_date=%s
                 AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
               ORDER BY updated_at DESC LIMIT 1""",
            (target_date, lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001),
        ).fetchone()
    if not row:
        return {"status": "not_scheduled", "next_update_at": None, "updating": False}
    return {
        "status": row["status"],
        "next_update_at": (
            row["next_run_at"].isoformat() if row.get("next_run_at") else None
        ),
        "updating": row["status"] == "running",
    }


def reschedule_job(job_id: str, snapshot_id: str, target_date: date) -> None:
    _, window_end = monitoring_window(target_date)
    now = datetime.now(timezone.utc)
    terminal = now >= window_end
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    next_run = min(
        current_hour + timedelta(hours=MONITOR_INTERVAL_HOURS), window_end
    )
    with _postgres_connection() as connection:
        connection.execute(
            """UPDATE monitoring_jobs
               SET status=%s, next_run_at=%s, locked_at=NULL, locked_by=NULL,
                   attempts=0, last_error=NULL, last_snapshot_id=%s,
                   completed_at=%s, updated_at=now()
               WHERE id=%s AND status='running'""",
            (
                "completed" if terminal else "pending",
                next_run,
                snapshot_id,
                now if terminal else None,
                job_id,
            ),
        )


def fail_job(job_id: str, error: Exception) -> None:
    message = f"{type(error).__name__}: {error}"[:1000]
    with _postgres_connection() as connection:
        row = connection.execute(
            "SELECT attempts FROM monitoring_jobs WHERE id=%s", (job_id,)
        ).fetchone()
        terminal = bool(row and row["attempts"] >= MONITOR_MAX_ATTEMPTS)
        connection.execute(
            """UPDATE monitoring_jobs SET status=%s, next_run_at=%s,
                      locked_at=NULL, locked_by=NULL, last_error=%s,
                      completed_at=%s, updated_at=now()
               WHERE id=%s AND status='running'""",
            (
                "cancelled" if terminal else "failed",
                datetime.now(timezone.utc) + timedelta(minutes=MONITOR_RETRY_MINUTES),
                message,
                datetime.now(timezone.utc) if terminal else None,
                job_id,
            ),
        )


def record_environmental_evidence(result: dict[str, Any]) -> None:
    """Populate the legacy wide evidence table for older API consumers.

    New code uses ``environmental_evidence`` and ``prediction_evidence_links``.
    The legacy row is conservatively marked as forecast because it combines
    inputs of several kinds and must never imply that all values were observed.
    """
    from psycopg.types.json import Jsonb

    conditions = result["current_conditions"]
    surface = result["surface_data"]
    observed_at = conditions.get("observed_at") or result["prediction_time"]
    with _postgres_connection() as connection:
        location = connection.execute(
            """INSERT INTO locations (lat,lon,name) VALUES (%s,%s,%s)
               ON CONFLICT (lat,lon) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
            (result["lat"], result["lon"], result["location_name"]),
        ).fetchone()
        connection.execute(
            """INSERT INTO environmental_observations
               (location_id, observed_at, source, value_kind, wind_speed_ms,
                wind_direction_deg, temperature_c, dewpoint_c, surface_pressure_hpa,
                precipitation_mm, soil_moisture, vegetation_water_content, aod,
                raw_payload)
               VALUES (%s,%s,'mixed-provider-inputs','forecast',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (location_id, observed_at, source, value_kind) DO NOTHING""",
            (
                location["id"], observed_at, conditions.get("wind_speed_ms"),
                conditions.get("wind_direction_deg"), conditions.get("temperature_c"),
                conditions.get("dewpoint_c"),
                conditions.get("surface_pressure_hpa"), conditions.get("precipitation_mm"),
                surface.get("soil_moisture"), surface.get("vegetation_water_content"),
                surface.get("prev_day_aod"), Jsonb({"input_quality": result.get("input_quality")}),
            ),
        )


def create_alert_level_event(
    tracking_key_value: str,
    snapshot_id: str,
    previous_level: str | None,
    result: dict[str, Any],
) -> str | None:
    current_level = result["alert_level"]
    completeness = float(
        result.get("data_composition", {}).get("input_completeness", 0)
    )
    location_name = str(result.get("location_name") or "").strip()
    # Clear, incomplete, unknown, and duplicate conditions remain in history
    # but never become outbound warning events.
    if (
        current_level == "clear"
        or current_level == previous_level
        or completeness < 0.8
        or not location_name
        or location_name.lower() == "unknown"
    ):
        return None
    from psycopg.types.json import Jsonb

    event_id = str(uuid.uuid4())
    aggregate_id = f"{tracking_key_value}:{snapshot_id}"
    levels = {"clear": 0, "watch": 1, "warning": 2, "alert": 3}
    direction = "initial" if previous_level is None else (
        "upgraded" if levels[current_level] > levels[previous_level] else "downgraded"
    )
    with _postgres_connection() as connection:
        connection.execute(
            """INSERT INTO outbox_events
               (id,event_type,aggregate_id,payload) VALUES (%s,%s,%s,%s)
               ON CONFLICT DO NOTHING""",
            (
                event_id, "prediction.alert_level_changed", aggregate_id,
                Jsonb({
                    "snapshot_id": snapshot_id,
                    "tracking_key": tracking_key_value,
                    "previous_level": previous_level,
                    "current_level": current_level,
                    "direction": direction,
                    "probability": result["probability"],
                    "message": result["alert_message"],
                    "location_name": result["location_name"],
                    "lat": result["lat"],
                    "lon": result["lon"],
                    "target_date": result["target_date"],
                }),
            ),
        )
    return event_id
