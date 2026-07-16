"""Alert subscriptions, notification feeds and durable outbox delivery state."""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from history_store import _postgres_connection

ALERT_WORKER_ID = os.getenv("ALERT_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
ALERT_MAX_ATTEMPTS = max(1, int(os.getenv("ALERT_MAX_ATTEMPTS", "8")))
LEVELS = {"clear": 0, "watch": 1, "warning": 2, "alert": 3}


def should_deliver(threshold: str, current_level: str, direction: str) -> bool:
    """Downgrades reach prior subscribers; upgrades respect their threshold."""
    return direction == "downgraded" or LEVELS.get(current_level, 0) >= LEVELS[threshold]


def list_subscriptions(phone_uid: str) -> list[dict[str, Any]]:
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT id,lat,lon,location_name,threshold,created_at
               FROM alert_subscriptions WHERE phone_uid=%s ORDER BY created_at""",
            (phone_uid,),
        ).fetchall()
    return [{**dict(row), "id": str(row["id"]), "created_at": row["created_at"].isoformat()} for row in rows]


def upsert_subscription(phone_uid: str, lat: float, lon: float, location_name: str, threshold: str) -> dict[str, Any]:
    if threshold not in {"watch", "warning", "alert"}:
        raise ValueError("threshold must be watch, warning or alert")
    with _postgres_connection() as connection:
        row = connection.execute(
            """INSERT INTO alert_subscriptions(phone_uid,lat,lon,location_name,threshold)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT(phone_uid,lat,lon) DO UPDATE SET
                 location_name=EXCLUDED.location_name,threshold=EXCLUDED.threshold
               RETURNING *""",
            (phone_uid, lat, lon, location_name, threshold),
        ).fetchone()
    return {**dict(row), "id": str(row["id"]), "created_at": row["created_at"].isoformat()}


def delete_subscription(phone_uid: str, subscription_id: str) -> bool:
    with _postgres_connection() as connection:
        result = connection.execute(
            "DELETE FROM alert_subscriptions WHERE id=%s AND phone_uid=%s",
            (subscription_id, phone_uid),
        )
    return result.rowcount > 0


def notification_feed(phone_uid: str, limit: int = 50) -> list[dict[str, Any]]:
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT DISTINCT e.id,e.event_type,e.payload,e.status,e.created_at
               FROM outbox_events e
               JOIN alert_subscriptions s ON s.phone_uid=%s
               WHERE e.event_type='prediction.alert_level_changed'
                 AND abs((e.payload->>'lat')::double precision-s.lat)<=0.05
                 AND abs((e.payload->>'lon')::double precision-s.lon)<=0.05
               ORDER BY e.created_at DESC LIMIT %s""",
            (phone_uid, limit),
        ).fetchall()
    items = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        items.append({
            "id": str(row["id"]), "event_type": row["event_type"], "status": row["status"],
            "created_at": row["created_at"].isoformat(), **payload,
        })
    return items


def heartbeat(worker_name: str, worker_id: str, status: str, metadata: dict | None = None) -> None:
    from psycopg.types.json import Jsonb
    with _postgres_connection() as connection:
        connection.execute(
            """INSERT INTO worker_heartbeats(worker_name,worker_id,status,metadata)
               VALUES (%s,%s,%s,%s) ON CONFLICT(worker_name) DO UPDATE SET
               worker_id=EXCLUDED.worker_id,status=EXCLUDED.status,
               metadata=EXCLUDED.metadata,heartbeat_at=now()""",
            (worker_name, worker_id, status, Jsonb(metadata or {})),
        )


def operational_status() -> dict[str, Any]:
    with _postgres_connection() as connection:
        counts = connection.execute(
            """SELECT
               count(*) filter(where status in ('pending','failed') and next_run_at<=now()) due_jobs,
               count(*) filter(where status='failed') failed_jobs
               FROM monitoring_jobs"""
        ).fetchone()
        outbox = connection.execute(
            """SELECT count(*) filter(where status in ('pending','failed')) pending,
                      count(*) filter(where status='failed') failed,
                      count(*) filter(where status='dead_letter') dead_letter FROM outbox_events"""
        ).fetchone()
        beats = connection.execute("SELECT * FROM worker_heartbeats").fetchall()
    now = datetime.now(timezone.utc)
    workers = {}
    for beat in beats:
        age = (now - beat["heartbeat_at"]).total_seconds()
        workers[beat["worker_name"]] = {
            "status": beat["status"], "fresh": age < 180,
            "heartbeat_at": beat["heartbeat_at"].isoformat(), "age_seconds": round(age),
        }
    return {
        "monitoring_jobs": dict(counts), "outbox": dict(outbox), "workers": workers,
    }


def claim_outbox_event() -> dict[str, Any] | None:
    with _postgres_connection() as connection:
        row = connection.execute(
            """WITH due AS (
                 SELECT id FROM outbox_events WHERE status IN ('pending','failed')
                   AND available_at<=now() AND attempts<%s
                 ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1
               ) UPDATE outbox_events e SET status='processing',attempts=e.attempts+1
               FROM due WHERE e.id=due.id RETURNING e.*""",
            (ALERT_MAX_ATTEMPTS,),
        ).fetchone()
    return dict(row) if row else None


def matching_recipients(event: dict[str, Any]) -> list[str]:
    payload = json.loads(event["payload"]) if isinstance(event["payload"], str) else event["payload"]
    if event["event_type"] != "prediction.alert_level_changed":
        return []
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT phone_uid,threshold FROM alert_subscriptions
               WHERE abs(lat-%s)<=0.05 AND abs(lon-%s)<=0.05""",
            (payload["lat"], payload["lon"]),
        ).fetchall()
    return [row["phone_uid"] for row in rows if should_deliver(
        row["threshold"], payload.get("current_level", "clear"), payload.get("direction", "initial")
    )]


def begin_delivery(event_id: str, phone_uid: str, snapshot_id: str | None) -> str | None:
    delivery_id = str(uuid.uuid4())
    with _postgres_connection() as connection:
        row = connection.execute(
            """INSERT INTO alert_deliveries(id,phone_uid,snapshot_id,outbox_event_id,status)
               VALUES (%s,%s,%s,%s,'processing')
               ON CONFLICT(outbox_event_id,phone_uid) WHERE outbox_event_id is not null and phone_uid is not null
               DO UPDATE SET status=CASE WHEN alert_deliveries.status='delivered'
                 THEN 'delivered' ELSE 'processing' END,updated_at=now()
               RETURNING id,status""",
            (delivery_id, phone_uid, snapshot_id, event_id),
        ).fetchone()
    return None if row["status"] == "delivered" else str(row["id"])


def finish_delivery(delivery_id: str, provider_id: str | None) -> None:
    with _postgres_connection() as connection:
        row = connection.execute(
            """UPDATE alert_deliveries SET status='delivered',provider_message_id=%s,
               updated_at=now() WHERE id=%s RETURNING phone_uid""", (provider_id, delivery_id)
        ).fetchone()
        if row:
            connection.execute(
                """INSERT INTO sms_messages(phone_uid,category,provider_message_id,status)
                   VALUES (%s,'alert',%s,'delivered')""", (row["phone_uid"], provider_id)
            )


def fail_delivery(delivery_id: str, error: Exception) -> None:
    with _postgres_connection() as connection:
        connection.execute(
            """UPDATE alert_deliveries SET status='failed',error_code=%s,
               updated_at=now() WHERE id=%s""", (type(error).__name__, delivery_id)
        )


def finish_event(event_id: str) -> None:
    with _postgres_connection() as connection:
        connection.execute(
            "UPDATE outbox_events SET status='delivered',processed_at=now(),last_error=NULL WHERE id=%s",
            (event_id,),
        )


def retry_event(event_id: str, error: Exception) -> None:
    with _postgres_connection() as connection:
        row = connection.execute("SELECT attempts FROM outbox_events WHERE id=%s", (event_id,)).fetchone()
        terminal = bool(row and row["attempts"] >= ALERT_MAX_ATTEMPTS)
        connection.execute(
            """UPDATE outbox_events SET status=%s,available_at=%s,last_error=%s,
               processed_at=%s WHERE id=%s""",
            (
                "dead_letter" if terminal else "failed",
                datetime.now(timezone.utc) + timedelta(minutes=min(60, 2 ** min(row["attempts"], 6))),
                f"{type(error).__name__}: {error}"[:1000],
                datetime.now(timezone.utc) if terminal else None, event_id,
            ),
        )
