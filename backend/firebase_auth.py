"""Firebase Authentication bridge for the existing PostgreSQL application."""

from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auth_store import AuthError, SESSION_DAYS, _country_calling_code, _delete_phone_account, _token_hash, hash_ip, normalize_phone
from history_store import _postgres_connection

_init_lock = threading.Lock()


def firebase_configured() -> bool:
    return bool(os.getenv("FIREBASE_PROJECT_ID", "").strip())


def _firebase_app():
    if not firebase_configured():
        raise AuthError(503, "Firebase phone authentication is not configured")
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise AuthError(503, "Firebase Admin is not installed") from exc
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    with _init_lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
            path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()
            options = {"projectId": os.environ["FIREBASE_PROJECT_ID"]}
            if raw:
                return firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)), options)
            if path:
                return firebase_admin.initialize_app(credentials.Certificate(Path(path)), options)
            return firebase_admin.initialize_app(options=options)


def verify_firebase_token(id_token: str, *, require_recent: bool = False) -> dict[str, Any]:
    if not id_token or len(id_token) > 10000:
        raise AuthError(401, "Firebase sign-in is required")
    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(id_token, app=_firebase_app(), check_revoked=True)
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError(401, "Firebase could not verify this sign-in") from exc
    phone = decoded.get("phone_number")
    if not phone:
        raise AuthError(400, "The Firebase account does not contain a verified phone number")
    if require_recent:
        auth_time = decoded.get("auth_time")
        if not auth_time or datetime.now(timezone.utc).timestamp() - float(auth_time) > 300:
            raise AuthError(401, "Verify your phone number again before deleting the account")
    return decoded


def create_firebase_session(
    id_token: str,
    purpose: str,
    preferred_location: dict[str, Any] | None,
    device_id: str | None,
    ip: str | None,
) -> dict[str, Any]:
    if purpose not in {"signup", "login"}:
        raise AuthError(400, "purpose must be signup or login")
    decoded = verify_firebase_token(id_token)
    firebase_uid = str(decoded["uid"])
    phone_uid = normalize_phone(str(decoded["phone_number"]))
    now = datetime.now(timezone.utc)
    with _postgres_connection() as connection:
        by_uid = connection.execute(
            "SELECT phone_uid FROM alert_identities WHERE firebase_uid=%s FOR UPDATE",
            (firebase_uid,),
        ).fetchone()
        by_phone = connection.execute(
            "SELECT phone_uid,firebase_uid FROM alert_identities WHERE phone_uid=%s FOR UPDATE",
            (phone_uid,),
        ).fetchone()
        if by_uid and by_uid["phone_uid"] != phone_uid:
            raise AuthError(409, "This Firebase identity is already linked to another phone account")
        exists = bool(by_phone)
        if purpose == "signup" and exists and by_phone["firebase_uid"] not in {None, firebase_uid}:
            raise AuthError(409, "This number is already linked. Log in instead.")
        if purpose == "login" and not exists:
            raise AuthError(404, "No SahelWatch account uses this number. Create an account instead.")
        location = preferred_location or {}
        if exists:
            connection.execute(
                """UPDATE alert_identities SET firebase_uid=%s,auth_provider='firebase',
                          verified_at=%s,updated_at=now() WHERE phone_uid=%s""",
                (firebase_uid, now, phone_uid),
            )
        else:
            connection.execute(
                """INSERT INTO alert_identities
                   (phone_uid,country_calling_code,verified_at,preferred_lat,
                    preferred_lon,preferred_location_name,firebase_uid,auth_provider)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'firebase')""",
                (phone_uid, _country_calling_code(phone_uid), now, location.get("lat"),
                 location.get("lon"), location.get("name"), firebase_uid),
            )
            if location.get("lat") is not None and location.get("lon") is not None:
                connection.execute(
                    """INSERT INTO alert_subscriptions
                       (phone_uid,lat,lon,location_name,threshold)
                       VALUES (%s,%s,%s,%s,'warning')
                       ON CONFLICT(phone_uid,lat,lon) DO NOTHING""",
                    (phone_uid, location["lat"], location["lon"], location.get("name") or "Preferred location"),
                )
        token = secrets.token_urlsafe(48)
        expires = now + timedelta(days=SESSION_DAYS)
        connection.execute(
            """INSERT INTO user_sessions(token_hash,phone_uid,ip_hash,expires_at)
               VALUES (%s,%s,%s,%s)""",
            (_token_hash(token), phone_uid, hash_ip(ip), expires),
        )
    return {"token": token, "phone_uid": phone_uid, "firebase_uid": firebase_uid, "expires_at": expires}


def _delete_firebase_user(firebase_uid: str) -> None:
    from firebase_admin import auth
    try:
        auth.delete_user(firebase_uid, app=_firebase_app())
    except auth.UserNotFoundError:
        return


def _finish_cleanup(firebase_uid: str, error: Exception | None = None) -> None:
    with _postgres_connection() as connection:
        if error is None:
            connection.execute(
                """UPDATE firebase_identity_cleanup SET status='completed',
                          completed_at=now(),last_error=NULL WHERE firebase_uid=%s""",
                (firebase_uid,),
            )
        else:
            connection.execute(
                """UPDATE firebase_identity_cleanup SET status='failed',
                          available_at=now()+interval '15 minutes',last_error=%s
                   WHERE firebase_uid=%s""",
                (f"{type(error).__name__}: {error}"[:1000], firebase_uid),
            )


def delete_firebase_account(session_user: dict[str, Any], id_token: str) -> None:
    decoded = verify_firebase_token(id_token, require_recent=True)
    firebase_uid = str(decoded["uid"])
    phone_uid = normalize_phone(str(decoded["phone_number"]))
    if phone_uid != session_user["phone_uid"]:
        raise AuthError(403, "This Firebase account does not match the signed-in account")
    with _postgres_connection() as connection:
        row = connection.execute(
            "SELECT firebase_uid FROM alert_identities WHERE phone_uid=%s FOR UPDATE",
            (phone_uid,),
        ).fetchone()
        if not row or row["firebase_uid"] != firebase_uid:
            raise AuthError(403, "This Firebase account is not linked to the signed-in account")
        connection.execute(
            """INSERT INTO firebase_identity_cleanup(firebase_uid)
               VALUES (%s) ON CONFLICT(firebase_uid) DO UPDATE SET
               status='pending',available_at=now(),last_error=NULL""",
            (firebase_uid,),
        )
        _delete_phone_account(connection, phone_uid)
    try:
        _delete_firebase_user(firebase_uid)
        _finish_cleanup(firebase_uid)
    except Exception as exc:
        # Application data is already deleted. A worker retries provider cleanup.
        _finish_cleanup(firebase_uid, exc)


def retry_one_firebase_cleanup() -> bool:
    """Claim and process one due identity cleanup without blocking alert delivery."""
    if not firebase_configured():
        return False
    with _postgres_connection() as connection:
        row = connection.execute(
            """WITH due AS (
                 SELECT firebase_uid FROM firebase_identity_cleanup
                 WHERE status IN ('pending','failed') AND available_at<=now() AND attempts<12
                 ORDER BY available_at FOR UPDATE SKIP LOCKED LIMIT 1
               )
               UPDATE firebase_identity_cleanup c SET status='processing',attempts=c.attempts+1
               FROM due WHERE c.firebase_uid=due.firebase_uid RETURNING c.firebase_uid"""
        ).fetchone()
    if not row:
        return False
    firebase_uid = row["firebase_uid"]
    try:
        _delete_firebase_user(firebase_uid)
        _finish_cleanup(firebase_uid)
    except Exception as exc:
        _finish_cleanup(firebase_uid, exc)
    return True
