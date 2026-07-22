"""Alert SMS provider adapters used during the Africa's Talking to Twilio transition."""

from __future__ import annotations

import asyncio
import os

from auth_store import AuthError, _send_sms as send_africas_talking_sms


def alert_provider_name() -> str:
    return os.getenv("ALERT_SMS_PROVIDER", "africastalking").strip().lower()


def twilio_configured() -> bool:
    destination = os.getenv("TWILIO_MESSAGING_SERVICE_SID") or os.getenv("TWILIO_FROM_NUMBER")
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and destination)


async def _send_twilio_sms(phone_uid: str, message: str) -> str:
    if not twilio_configured():
        raise AuthError(503, "Twilio alert delivery is not configured")
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise AuthError(503, "Twilio support is not installed") from exc

    def send() -> str:
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        fields = {"to": f"+{phone_uid}", "body": message}
        messaging_service = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "").strip()
        if messaging_service:
            fields["messaging_service_sid"] = messaging_service
        else:
            fields["from_"] = os.environ["TWILIO_FROM_NUMBER"]
        return str(client.messages.create(**fields).sid)

    try:
        return await asyncio.to_thread(send)
    except Exception as exc:
        raise AuthError(502, "Twilio could not deliver this alert") from exc


async def send_alert_sms(phone_uid: str, message: str) -> tuple[str | None, str]:
    provider = alert_provider_name()
    if provider == "twilio":
        return await _send_twilio_sms(phone_uid, message), provider
    if provider == "africastalking":
        return await send_africas_talking_sms(phone_uid, message), provider
    raise AuthError(503, "ALERT_SMS_PROVIDER must be twilio or africastalking")
