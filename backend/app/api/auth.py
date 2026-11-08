import secrets
import io
import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.errors import AppError
from app.models import User, Session as AuthSession, now
from app.schemas import Login, PasswordChange, TotpCode
from app.security.auth import verify_password, hash_password, create_session, set_session_cookie, current_session, current_user, rate_limit, token_hash, new_totp, fernet, check_totp, recovery_codes, audit, _dummy
from app.services.settings import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/session")
def session_info(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user, session = current_session(request, response, db)
        return {"authenticated": True, "auth_disabled": settings.auth_disabled, "user": {"username": user.username, "totp_enabled": user.totp_enabled}, "csrf_token": session.csrf_token, "app_name": get_settings(db, user.id)["app_name"], "expires_at": session.expires_at.isoformat() + "Z"}
    except AppError:
        csrf = request.cookies.get("omnifix_csrf") or secrets.token_urlsafe(32)
        response.set_cookie("omnifix_csrf", csrf, httponly=False, secure=settings.cookie_secure_effective, samesite=settings.cookie_samesite_effective, max_age=3600, path="/")
        return {"authenticated": False, "auth_disabled": settings.auth_disabled, "csrf_token": csrf, "app_name": settings.app_name}


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    rate_limit(db, f"login:{ip}", settings.login_attempts, settings.login_window_minutes)
    rate_limit(db, "login:global", settings.login_attempts * 4, settings.login_window_minutes)
    user = db.scalar(select(User).where(User.username == body.username.strip()))
    if not verify_password(body.password, user.password_hash if user else _dummy) or not user:
        audit(db, "login.failed")
        db.commit()
        raise AppError("invalid_credentials", "The username, password or verification code is incorrect.", 401)
    if hasher_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    if user.totp_enabled:
        valid = check_totp(user.totp_secret, body.totp_code)
        if not valid:
            for index, encoded in enumerate(user.recovery_codes):
                if verify_password(body.totp_code, encoded):
                    codes = list(user.recovery_codes)
                    codes.pop(index)
                    user.recovery_codes = codes
                    valid = True
                    break
        if not valid:
            raise AppError("totp_required", "Enter your authenticator code or an unused recovery code.", 401)
    token = create_session(db, user, request)
    set_session_cookie(response, token)
    response.delete_cookie("omnifix_csrf", path="/")
    session = db.get(AuthSession, token_hash(token))
    return {"authenticated": True, "user": {"username": user.username, "totp_enabled": user.totp_enabled}, "csrf_token": session.csrf_token}


def hasher_needs_rehash(encoded):
    from app.security.auth import hasher
    return hasher.check_needs_rehash(encoded)


@router.post("/logout")
def logout(response: Response, auth: tuple = Depends(current_session), db: Session = Depends(get_db)):
    auth[1].revoked = True
    audit(db, "logout")
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked=True))
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.post("/password/change")
def change_password(body: PasswordChange, request: Request, auth: tuple = Depends(current_session), db: Session = Depends(get_db)):
    user, session = auth
    rate_limit(db, f"password:{user.id}", 5, 15)
    if not verify_password(body.current_password, user.password_hash):
        raise AppError("invalid_password", "The current password is incorrect.", 403)
    if body.current_password == body.new_password:
        raise AppError("invalid_password", "Choose a different new password.")
    user.password_hash = hash_password(body.new_password)
    db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != session.token_hash).values(revoked=True))
    audit(db, "password.changed")
    db.commit()
    return {"ok": True, "message": "Password changed. Other sessions were signed out."}


@router.post("/totp/setup")
def totp_setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.totp_enabled:
        raise AppError("totp_enabled", "Two-factor authentication is already enabled.", 409)
    secret = new_totp()
    user.totp_secret = fernet().encrypt(secret.encode()).decode()
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name="OmniFix Private Scanner")
    qr = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buffer = io.BytesIO()
    qr.save(buffer)
    return {"secret": secret, "uri": uri, "qr_svg": buffer.getvalue().decode()}


@router.post("/totp/enable")
def totp_enable(body: TotpCode, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"totp:{user.id}", 5, 15)
    if not verify_password(body.password, user.password_hash) or not user.totp_secret or not check_totp(user.totp_secret, body.code):
        raise AppError("invalid_totp", "Password or authenticator code is incorrect.", 403)
    plain, hashed = recovery_codes()
    user.totp_enabled, user.recovery_codes = True, hashed
    audit(db, "totp.enabled")
    db.commit()
    return {"enabled": True, "recovery_codes": plain}


@router.post("/totp/disable")
def totp_disable(body: TotpCode, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"totp:{user.id}", 5, 15)
    if not user.totp_enabled or not verify_password(body.password, user.password_hash) or not check_totp(user.totp_secret, body.code):
        raise AppError("invalid_totp", "Password or authenticator code is incorrect.", 403)
    user.totp_enabled, user.totp_secret, user.recovery_codes = False, None, []
    audit(db, "totp.disabled")
    db.commit()
    return {"enabled": False}
