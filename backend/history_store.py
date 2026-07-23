"""Durable PostgreSQL prediction history and progressive state.

DigitalOcean Managed PostgreSQL is authoritative when ``DATABASE_URL`` is set.
SQLite is retained only for explicit local development and tests. Production
can set ``DATABASE_REQUIRED=true`` to fail closed instead of silently losing
history to an ephemeral local file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "90"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_REQUIRED = os.getenv("DATABASE_REQUIRED", "false").lower() == "true"
SQLITE_PATH = Path(os.getenv("HISTORY_DB_PATH", Path(__file__).with_name("sahelwatch_history.db")))
DB_POOL_SIZE = max(2, int(os.getenv("DB_POOL_SIZE", "6")))
_POSTGRES_POOL = None
_POSTGRES_POOL_LOCK = threading.Lock()


def _using_postgres() -> bool:
    if DATABASE_REQUIRED and not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required in this deployment")
    return bool(DATABASE_URL)


@contextmanager
def _postgres_connection() -> Iterator[Any]:
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeError("Install psycopg[binary] and psycopg-pool to use DATABASE_URL") from exc
    global _POSTGRES_POOL
    if _POSTGRES_POOL is None:
        with _POSTGRES_POOL_LOCK:
            if _POSTGRES_POOL is None:
                pool = ConnectionPool(
                    conninfo=DATABASE_URL,
                    min_size=0,
                    max_size=DB_POOL_SIZE,
                    kwargs={"row_factory": dict_row, "connect_timeout": 10},
                    open=False,
                    name="sahelwatch-postgres",
                )
                pool.open(wait=True, timeout=15)
                _POSTGRES_POOL = pool
    with _POSTGRES_POOL.connection(timeout=10) as connection:
        yield connection


@contextmanager
def _sqlite_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS prediction_snapshots (
                id TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL,
                location_name TEXT NOT NULL, target_date TEXT NOT NULL,
                recorded_at TEXT NOT NULL, probability REAL NOT NULL,
                alert_level TEXT NOT NULL, dust_event INTEGER NOT NULL,
                data_source TEXT NOT NULL, model_version TEXT, metadata TEXT NOT NULL DEFAULT '{}'
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_lookup ON prediction_snapshots(target_date, lat, lon)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_retention ON prediction_snapshots(recorded_at)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS progressive_prediction_state (
                tracking_key TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL,
                target_date TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def database_status() -> dict[str, Any]:
    """Readiness probe without exposing credentials or host details."""
    try:
        if _using_postgres():
            with _postgres_connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return {"available": True, "engine": "postgresql"}
        with _sqlite_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"available": True, "engine": "sqlite-local"}
    except Exception as exc:
        return {"available": False, "engine": "postgresql" if DATABASE_URL else "unconfigured", "error": type(exc).__name__}


def purge_expired() -> None:
    cutoff = _cutoff()
    if _using_postgres():
        with _postgres_connection() as connection:
            connection.execute("DELETE FROM prediction_snapshots WHERE recorded_at < %s", (cutoff,))
            connection.execute("DELETE FROM progressive_prediction_state WHERE updated_at < %s", (cutoff,))
        return
    with _sqlite_connection() as connection:
        connection.execute("DELETE FROM prediction_snapshots WHERE recorded_at < ?", (cutoff.isoformat(),))
        connection.execute("DELETE FROM progressive_prediction_state WHERE updated_at < ?", (cutoff.isoformat(),))


def save_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Persist an immutable prediction revision and return its stored identity."""
    record = {
        "id": str(uuid.uuid4()), "lat": float(snapshot["lat"]), "lon": float(snapshot["lon"]),
        "location_name": snapshot["location_name"], "target_date": str(snapshot["target_date"]),
        "recorded_at": snapshot.get("recorded_at") or datetime.now(timezone.utc).isoformat(),
        "probability": float(snapshot["probability"]), "alert_level": snapshot["alert_level"],
        "dust_event": bool(snapshot["dust_event"]), "data_source": snapshot.get("data_source", "open-meteo+gee"),
        "model_version": snapshot.get("model_version"), "metadata": snapshot.get("metadata", {}),
        "revision_reason": snapshot.get("revision_reason", "scheduled_evidence_refresh"),
        "evidence_fingerprint": snapshot.get("evidence_fingerprint"),
        "observed_fraction": snapshot.get("observed_fraction"),
        "forecast_fraction": snapshot.get("forecast_fraction"),
        "input_completeness": snapshot.get("input_completeness"),
    }
    purge_expired()
    if _using_postgres():
        from psycopg.types.json import Jsonb
        with _postgres_connection() as connection:
            lock_key = (
                f"revision:{record['lat']:.3f}:{record['lon']:.3f}:"
                f"{record['target_date']}"
            )
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )
            revision_row = connection.execute(
                """SELECT coalesce(max(revision_number), 0) + 1 AS next_revision
                   FROM prediction_snapshots
                   WHERE target_date=%s
                     AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s""",
                (
                    record["target_date"],
                    record["lat"] - 0.001,
                    record["lat"] + 0.001,
                    record["lon"] - 0.001,
                    record["lon"] + 0.001,
                ),
            ).fetchone()
            record["revision_number"] = int(revision_row["next_revision"])
            inserted = connection.execute(
                """INSERT INTO prediction_snapshots
                   (id, lat, lon, location_name, target_date, recorded_at, probability,
                    alert_level, dust_event, data_source, model_version, metadata,
                    revision_number,revision_reason,evidence_fingerprint,
                    observed_fraction,forecast_fraction,input_completeness)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING RETURNING id""",
                (record["id"], record["lat"], record["lon"], record["location_name"], record["target_date"],
                 record["recorded_at"], record["probability"], record["alert_level"], record["dust_event"],
                 record["data_source"], record["model_version"], Jsonb(record["metadata"]),
                 record["revision_number"], record["revision_reason"],
                 record["evidence_fingerprint"], record["observed_fraction"],
                 record["forecast_fraction"], record["input_completeness"]),
            ).fetchone()
            if not inserted and record["evidence_fingerprint"]:
                existing = connection.execute(
                    """SELECT id,revision_number FROM prediction_snapshots
                       WHERE target_date=%s
                         AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
                         AND evidence_fingerprint=%s LIMIT 1""",
                    (
                        record["target_date"],
                        record["lat"] - 0.001,
                        record["lat"] + 0.001,
                        record["lon"] - 0.001,
                        record["lon"] + 0.001,
                        record["evidence_fingerprint"],
                    ),
                ).fetchone()
                record["id"] = str(existing["id"])
                record["revision_number"] = int(existing["revision_number"])
        return record
    with _sqlite_connection() as connection:
        connection.execute(
            """INSERT INTO prediction_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record["id"], record["lat"], record["lon"], record["location_name"], record["target_date"],
             record["recorded_at"], record["probability"], record["alert_level"], int(record["dust_event"]),
             record["data_source"], record["model_version"], json.dumps(record["metadata"])),
        )
    return record


def _normalise_row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["id"] = str(item["id"])
    item["target_date"] = str(item["target_date"])
    item["recorded_at"] = item["recorded_at"].isoformat() if hasattr(item["recorded_at"], "isoformat") else item["recorded_at"]
    item["dust_event"] = bool(item["dust_event"])
    if isinstance(item.get("metadata"), str):
        item["metadata"] = json.loads(item["metadata"])
    return item


def query_snapshots(lat: float, lon: float, target_date: date) -> list[dict[str, Any]]:
    sql = """SELECT * FROM prediction_snapshots WHERE target_date = %s
             AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s ORDER BY recorded_at DESC"""
    params = (target_date, lat - 0.05, lat + 0.05, lon - 0.05, lon + 0.05)
    if _using_postgres():
        with _postgres_connection() as connection:
            return [_normalise_row(row) for row in connection.execute(sql, params).fetchall()]
    with _sqlite_connection() as connection:
        rows = connection.execute(sql.replace("%s", "?"), (target_date.isoformat(), *params[1:])).fetchall()
    return [_normalise_row(row) for row in rows]


def query_recent_snapshots(lat: float, lon: float, limit: int = 10) -> list[dict[str, Any]]:
    sql = """SELECT * FROM prediction_snapshots WHERE lat BETWEEN %s AND %s
             AND lon BETWEEN %s AND %s ORDER BY recorded_at DESC LIMIT %s"""
    params = (lat - 0.05, lat + 0.05, lon - 0.05, lon + 0.05, limit)
    if _using_postgres():
        with _postgres_connection() as connection:
            return [_normalise_row(row) for row in connection.execute(sql, params).fetchall()]
    with _sqlite_connection() as connection:
        rows = connection.execute(sql.replace("%s", "?"), params).fetchall()
    return [_normalise_row(row) for row in rows]


def query_latest_environmental_evidence(lat: float, lon: float) -> dict[str, Any] | None:
    if not _using_postgres():
        return None
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT e.observed_at,e.received_at,e.wind_speed_ms,
                      e.wind_direction_deg,e.temperature_c,e.dewpoint_c,
                      e.surface_pressure_hpa,e.precipitation_mm,e.soil_moisture,
                      e.vegetation_water_content,e.aod,e.raw_payload
               FROM environmental_observations e JOIN locations l ON l.id=e.location_id
               WHERE l.lat BETWEEN %s AND %s AND l.lon BETWEEN %s AND %s
               ORDER BY e.received_at DESC LIMIT 1""",
            (lat - 0.05, lat + 0.05, lon - 0.05, lon + 0.05),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    for key in ("observed_at", "received_at"):
        item[key] = item[key].isoformat() if item.get(key) else None
    if isinstance(item.get("raw_payload"), str):
        item["raw_payload"] = json.loads(item["raw_payload"])
    return item


def query_latest_prediction_bundle(
    lat: float,
    lon: float,
    target_date: date,
    *,
    allow_recent_fallback: bool = True,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read the central snapshot and its evidence over one database connection.

    Retention is enforced by the daily worker job. A dashboard read must remain
    read-only and must not open extra TLS connections merely to run cleanup.
    """
    if not _using_postgres():
        snapshots = query_snapshots(lat, lon, target_date)
        if not snapshots and allow_recent_fallback:
            snapshots = query_recent_snapshots(lat, lon, 1)
        return (snapshots[0] if snapshots else None), None

    snapshot_sql = """SELECT * FROM prediction_snapshots
                      WHERE target_date=%s
                        AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
                      ORDER BY recorded_at DESC LIMIT 1"""
    recent_sql = """SELECT * FROM prediction_snapshots
                    WHERE lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
                    ORDER BY recorded_at DESC LIMIT 1"""
    evidence_sql = """SELECT e.observed_at,e.received_at,e.wind_speed_ms,
                             e.wind_direction_deg,e.temperature_c,e.dewpoint_c,
                             e.surface_pressure_hpa,e.precipitation_mm,e.soil_moisture,
                             e.vegetation_water_content,e.aod,e.raw_payload
                      FROM environmental_observations e
                      JOIN locations l ON l.id=e.location_id
                      WHERE l.lat BETWEEN %s AND %s AND l.lon BETWEEN %s AND %s
                      ORDER BY e.received_at DESC LIMIT 1"""
    bounds = (lat - 0.05, lat + 0.05, lon - 0.05, lon + 0.05)
    with _postgres_connection() as connection:
        snapshot_row = connection.execute(
            snapshot_sql, (target_date, *bounds)
        ).fetchone()
        if not snapshot_row and allow_recent_fallback:
            snapshot_row = connection.execute(recent_sql, bounds).fetchone()
        evidence_row = connection.execute(evidence_sql, bounds).fetchone()

    snapshot = _normalise_row(snapshot_row) if snapshot_row else None
    evidence = dict(evidence_row) if evidence_row else None
    if evidence:
        for key in ("observed_at", "received_at"):
            evidence[key] = evidence[key].isoformat() if evidence.get(key) else None
        if isinstance(evidence.get("raw_payload"), str):
            evidence["raw_payload"] = json.loads(evidence["raw_payload"])
    return snapshot, evidence


def query_latest_outlooks(
    lat: float, lon: float, target_dates: list[date]
) -> list[dict[str, Any]]:
    """Return at most one central revision for each requested calendar day."""
    if not target_dates:
        return []
    if not _using_postgres():
        results = []
        for target_date in target_dates:
            rows = query_snapshots(lat, lon, target_date)
            if rows:
                results.append(rows[0])
        return results
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT DISTINCT ON (target_date) *
               FROM prediction_snapshots
               WHERE target_date = ANY(%s)
                 AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s
               ORDER BY target_date,recorded_at DESC""",
            (
                target_dates,
                lat - 0.05,
                lat + 0.05,
                lon - 0.05,
                lon + 0.05,
            ),
        ).fetchall()
    normalized = [_normalise_row(row) for row in rows]
    by_date = {item["target_date"]: item for item in normalized}
    return [
        by_date[target.isoformat()]
        for target in target_dates
        if target.isoformat() in by_date
    ]


def load_progressive_state(tracking_key: str) -> dict[str, Any] | None:
    if _using_postgres():
        with _postgres_connection() as connection:
            row = connection.execute(
                "SELECT state FROM progressive_prediction_state WHERE tracking_key = %s", (tracking_key,)
            ).fetchone()
    else:
        with _sqlite_connection() as connection:
            row = connection.execute(
                "SELECT state FROM progressive_prediction_state WHERE tracking_key = ?", (tracking_key,)
            ).fetchone()
    if not row:
        return None
    state = row["state"]
    return json.loads(state) if isinstance(state, str) else state


def save_progressive_state(tracking_key: str, state: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    if _using_postgres():
        from psycopg.types.json import Jsonb
        with _postgres_connection() as connection:
            connection.execute(
                """INSERT INTO progressive_prediction_state
                   (tracking_key, lat, lon, target_date, state, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (tracking_key) DO UPDATE SET state=EXCLUDED.state, updated_at=EXCLUDED.updated_at""",
                (tracking_key, state["lat"], state["lon"], state["target_date"], Jsonb(state), now),
            )
        return
    with _sqlite_connection() as connection:
        connection.execute(
            """INSERT INTO progressive_prediction_state VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(tracking_key) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at""",
            (tracking_key, state["lat"], state["lon"], state["target_date"], json.dumps(state), now.isoformat()),
        )


def query_active_progressive_states() -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    if _using_postgres():
        with _postgres_connection() as connection:
            rows = connection.execute(
                "SELECT state FROM progressive_prediction_state WHERE target_date >= %s ORDER BY updated_at DESC", (cutoff,)
            ).fetchall()
    else:
        with _sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT state FROM progressive_prediction_state WHERE target_date >= ? ORDER BY updated_at DESC", (cutoff.isoformat(),)
            ).fetchall()
    return [json.loads(row["state"]) if isinstance(row["state"], str) else row["state"] for row in rows]
