"""Phone OTP identity and session persistence for SahelWatch."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import phonenumbers

from history_store import _postgres_connection

PHONE_RE = re.compile(r"^[1-9][0-9]{9,14}$")
OTP_TTL_MINUTES = 10
SESSION_DAYS = 30
MAX_OTP_ATTEMPTS = 5


class AuthError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not PHONE_RE.fullmatch(digits):
        raise AuthError(400, "Enter a complete international phone number including country code")
    parsed = phonenumbers.parse(f"+{digits}", None)
    if not phonenumbers.is_valid_number(parsed):
        raise AuthError(400, "This is not a valid international phone number")
    return digits


def _country_calling_code(phone_uid: str) -> str:
    return str(phonenumbers.parse(f"+{phone_uid}", None).country_code)


def _pepper() -> str:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < 32:
        raise AuthError(503, "Phone authentication is not configured")
    return value


def _digest(value: str) -> str:
    return hmac.new(_pepper().encode(), value.encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_ip(ip: str | None) -> str | None:
    return _digest(f"ip:{ip}") if ip else None


def account_exists(phone_uid: str) -> bool:
    with _postgres_connection() as connection:
        return connection.execute(
            "SELECT 1 FROM alert_identities WHERE phone_uid=%s", (phone_uid,)
        ).fetchone() is not None


async def _send_sms(phone_uid: str, message: str) -> str | None:
    username = os.getenv("AFRICASTALKING_USERNAME", "")
    api_key = os.getenv("AFRICASTALKING_API_KEY", "")
    if not username or not api_key:
        raise AuthError(503, "SMS verification is not configured")
    sandbox = os.getenv("AFRICASTALKING_SANDBOX", "false").lower() == "true"
    url = "https://api.sandbox.africastalking.com/version1/messaging" if sandbox else "https://api.africastalking.com/version1/messaging"
    data = {"username": username, "to": f"+{phone_uid}", "message": message}
    sender = os.getenv("AFRICASTALKING_SENDER_ID", "").strip()
    if sender:
        data["from"] = sender
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers={"apiKey": api_key, "Accept": "application/json"}, data=data)
    if response.status_code >= 400:
        raise AuthError(502, "The SMS provider rejected the verification request")
    payload = response.json()
    recipients = payload.get("SMSMessageData", {}).get("Recipients", [])
    if not recipients or recipients[0].get("status") not in {"Success", "Sent"}:
        raise AuthError(502, "The verification message could not be sent to this number")
    return recipients[0].get("messageId")


async def request_otp(phone: str, purpose: str, device_id: str | None, ip: str | None) -> dict[str, Any]:
    phone_uid = normalize_phone(phone)
    exists = account_exists(phone_uid)
    if purpose == "signup" and exists:
        raise AuthError(409, "This number is already linked. Log in instead.")
    if purpose == "login" and not exists:
        raise AuthError(404, "No account uses this number. Create an account instead.")
    now = datetime.now(timezone.utc)
    with _postgres_connection() as connection:
        recent = connection.execute(
            "SELECT created_at FROM otp_challenges WHERE phone_uid=%s ORDER BY created_at DESC LIMIT 1", (phone_uid,)
        ).fetchone()
        if recent and now - recent["created_at"] < timedelta(seconds=60):
            raise AuthError(429, "Wait one minute before requesting another code")
    code = f"{secrets.randbelow(1_000_000):06d}"
    provider_id = await _send_sms(phone_uid, f"Your SahelWatch verification code is {code}. It expires in 10 minutes.")
    challenge_id = str(uuid.uuid4())
    try:
        parsed_device = uuid.UUID(device_id) if device_id else None
    except ValueError as exc:
        raise AuthError(400, "Invalid device identifier") from exc
    with _postgres_connection() as connection:
        connection.execute(
            """INSERT INTO otp_challenges
               (id, phone_uid, purpose, code_hash, expires_at, requested_ip_hash, device_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (challenge_id, phone_uid, purpose, _digest(f"{challenge_id}:{code}"),
             now + timedelta(minutes=OTP_TTL_MINUTES), hash_ip(ip), parsed_device),
        )
        connection.execute(
            """INSERT INTO sms_messages(phone_uid, category, provider_message_id, status)
               VALUES (%s,'otp',%s,'submitted')""", (phone_uid, provider_id)
        )
    return {"challenge_id": challenge_id, "expires_in_seconds": OTP_TTL_MINUTES * 60}


def verify_otp(challenge_id: str, code: str, preferred_location: dict[str, Any] | None, ip: str | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _postgres_connection() as connection:
        row = connection.execute(
            "SELECT * FROM otp_challenges WHERE id=%s FOR UPDATE", (challenge_id,)
        ).fetchone()
        if not row or row["consumed_at"]:
            raise AuthError(400, "This verification request is no longer valid")
        if row["expires_at"] < now:
            raise AuthError(400, "The verification code has expired. Request a new one.")
        if row["attempts"] >= MAX_OTP_ATTEMPTS:
            raise AuthError(429, "Too many incorrect attempts. Request a new code.")
        expected = _digest(f"{challenge_id}:{code}")
        if not hmac.compare_digest(row["code_hash"], expected):
            connection.execute("UPDATE otp_challenges SET attempts=attempts+1 WHERE id=%s", (challenge_id,))
            raise AuthError(400, "The verification code is incorrect")
        phone_uid = row["phone_uid"]
        if row["purpose"] == "signup":
            location = preferred_location or {}
            connection.execute(
                """INSERT INTO alert_identities
                   (phone_uid, country_calling_code, verified_at, preferred_lat, preferred_lon, preferred_location_name)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (phone_uid, _country_calling_code(phone_uid), now, location.get("lat"), location.get("lon"), location.get("name")),
            )
        connection.execute("UPDATE otp_challenges SET consumed_at=%s WHERE id=%s", (now, challenge_id))
        token = secrets.token_urlsafe(48)
        expires = now + timedelta(days=SESSION_DAYS)
        connection.execute(
            """INSERT INTO user_sessions(token_hash, phone_uid, device_id, ip_hash, expires_at)
               VALUES (%s,%s,%s,%s,%s)""",
            (_token_hash(token), phone_uid, row["device_id"], hash_ip(ip), expires),
        )
        if row["device_id"]:
            connection.execute(
                """INSERT INTO known_devices(device_id, phone_uid, first_ip_hash, last_ip_hash)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT(device_id) DO UPDATE SET phone_uid=EXCLUDED.phone_uid,
                   last_ip_hash=EXCLUDED.last_ip_hash,last_seen_at=now()""",
                (row["device_id"], phone_uid, hash_ip(ip), hash_ip(ip)),
            )
    return {"token": token, "phone_uid": phone_uid, "expires_at": expires}


def session_user(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT i.phone_uid,i.preferred_lat,i.preferred_lon,i.preferred_location_name
               FROM user_sessions s JOIN alert_identities i USING(phone_uid)
               WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>now()""",
            (_token_hash(token),),
        ).fetchone()
        if row:
            connection.execute("UPDATE user_sessions SET last_seen_at=now() WHERE token_hash=%s", (_token_hash(token),))
        return dict(row) if row else None


def revoke_session(token: str | None) -> None:
    if token:
        with _postgres_connection() as connection:
            connection.execute("UPDATE user_sessions SET revoked_at=now() WHERE token_hash=%s", (_token_hash(token),))
