from datetime import timedelta
import base64, hashlib, secrets
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography.fernet import Fernet
import pyotp
from sqlalchemy import select, delete
from fastapi import Request, Response, Depends
from sqlalchemy.orm import Session as DbSession
from app.core.database import get_db
from app.core.config import settings
from app.core.errors import AppError
from app.models import User, Session, RateLimit, AuditEvent, now

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
_dummy = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def audit(db: DbSession, event: str):
    db.add(AuditEvent(event=event))


def rate_limit(db: DbSession, key: str, limit: int, minutes: int):
    key = token_hash(key)
    cutoff = now() - timedelta(minutes=minutes)
    db.execute(delete(RateLimit).where(RateLimit.window_start < cutoff))
    row = db.get(RateLimit, key)
    if row is None or row.window_start < cutoff:
        row = RateLimit(key=key, count=0, window_start=now())
        db.add(row)
    row.count += 1
    db.commit()
    if row.count > limit:
        raise AppError("rate_limited", "Too many attempts. Please wait before trying again.", 429)


def create_session(db: DbSession, user: User, request: Request) -> str:
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=token_hash(token), user_id=user.id, csrf_token=secrets.token_urlsafe(32), user_agent=request.headers.get("user-agent", "")[:200], expires_at=now() + timedelta(hours=settings.session_hours)))
    user.last_login = now()
    audit(db, "login.success")
    db.commit()
    return token


def set_session_cookie(response, token: str):
    response.set_cookie(settings.cookie_name, token, httponly=True, secure=settings.cookie_secure_effective, samesite=settings.cookie_samesite_effective, max_age=settings.session_hours * 3600, path="/")


def current_session(request: Request, response: Response, db: DbSession = Depends(get_db)) -> tuple[User, Session]:
    token = request.cookies.get(settings.cookie_name)
    row = db.get(Session, token_hash(token)) if token else None
    valid = bool(row and not row.revoked and row.expires_at > now() and row.last_seen >= now() - timedelta(minutes=settings.session_idle_minutes))
    if not valid and settings.auth_disabled:
        # Opt-in no-login mode: transparently sign in the single owner so the
        # app opens without a sign-in page. CSRF protection stays enabled.
        owner = db.scalar(select(User).order_by(User.created_at).limit(1))
        if owner:
            if row and row.user_id == owner.id and not row.revoked:
                # Refresh the existing session in place so the cookie and CSRF
                # token stay stable. Otherwise a background poll after idle
                # expiry would rotate the cookie while the page keeps the old
                # CSRF token, causing "Security token missing or invalid".
                row.expires_at = now() + timedelta(hours=settings.session_hours)
                row.last_seen = now()
                db.commit()
                request.state.owner = owner
                request.state.session = row
                return owner, row
            token = create_session(db, owner, request)
            set_session_cookie(response, token)
            row = db.get(Session, token_hash(token))
            request.state.owner = owner
            request.state.session = row
            return owner, row
    if not valid:
        raise AppError("unauthorized", "Your session has expired. Please sign in again.", 401)
    user = db.get(User, row.user_id)
    if not user:
        raise AppError("unauthorized", "Please sign in to continue.", 401)
    row.last_seen = now()
    db.commit()
    request.state.owner = user
    request.state.session = row
    return user, row


def current_user(auth: tuple[User, Session] = Depends(current_session)) -> User:
    return auth[0]


def fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256((settings.secret + ":totp").encode()).digest()))


def new_totp() -> str:
    return pyotp.random_base32()


def check_totp(secret_encrypted: str, code: str) -> bool:
    try:
        secret = fernet().decrypt(secret_encrypted.encode()).decode()
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False


def recovery_codes() -> tuple[list[str], list[str]]:
    plain = [secrets.token_hex(5) for _ in range(8)]
    return plain, [hash_password(c) for c in plain]
