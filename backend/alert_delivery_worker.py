"""Deliver threshold-change outbox events to subscribed phone accounts."""

from __future__ import annotations

import asyncio
import json
import os

from alert_store import (
    ALERT_WORKER_ID, begin_delivery, claim_outbox_event, fail_delivery,
    finish_delivery, finish_event, heartbeat, matching_recipients, retry_event,
)
from auth_store import send_alert_sms

POLL_SECONDS = max(5, int(os.getenv("ALERT_WORKER_POLL_SECONDS", "15")))


async def process_event(event: dict) -> None:
    payload = json.loads(event["payload"]) if isinstance(event["payload"], str) else event["payload"]
    failures = []
    for phone_uid in matching_recipients(event):
        delivery_id = begin_delivery(str(event["id"]), phone_uid, payload.get("snapshot_id"))
        if not delivery_id:
            continue
        try:
            provider_id = await send_alert_sms(phone_uid, payload["message"])
            finish_delivery(delivery_id, provider_id)
        except Exception as exc:
            fail_delivery(delivery_id, exc)
            failures.append(exc)
    if failures:
        raise failures[0]
    finish_event(str(event["id"]))


async def run_forever() -> None:
    print(f"SahelWatch alert delivery worker started: {ALERT_WORKER_ID}")
    while True:
        try:
            heartbeat("alert-delivery", ALERT_WORKER_ID, "running")
            event = claim_outbox_event()
            if not event:
                await asyncio.sleep(POLL_SECONDS)
                continue
            try:
                await process_event(event)
            except Exception as exc:
                retry_event(str(event["id"]), exc)
                print(f"Outbox event {event['id']} failed: {type(exc).__name__}: {exc}")
        except Exception as exc:
            print(f"Alert worker loop error: {type(exc).__name__}: {exc}")
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
