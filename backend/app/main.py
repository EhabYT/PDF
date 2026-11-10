import secrets
import logging
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException
from app.core.config import settings
from app.core.errors import AppError
from app.api import auth, documents, pages, jobs, exports, settings as settings_api, security, dashboard

if settings.environment == "production" and not settings.session_secret:
    raise RuntimeError("Production requires an explicit SESSION_SECRET environment variable")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("omnifix.api")
if settings.auth_disabled:
    log.warning("AUTH_DISABLED=true: the sign-in page is removed and the owner is auto-authenticated. Anyone who can reach this URL has full owner access. Only run this behind Cloudflare Access, a VPN, or a trusted private network.")
app = FastAPI(title="OmniFix Private Scanner API", version="1.0.0", docs_url="/api/docs" if settings.environment != "production" else None, redoc_url=None, openapi_url="/api/openapi.json" if settings.environment != "production" else None)
_cors_origins = list(settings.origins)
# Opt-in: sandboxed iframes without allow-same-origin have the opaque origin
# "null". Required only for the cookie-less embedded-preview transport.
if settings.allow_opaque_origin and settings.auth_disabled:
    _cors_origins.append("null")
if _cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-CSRF-Token", "X-Session-Token"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in settings.trusted_hosts.split(",")])


@app.middleware("http")
async def private_security(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin") or ""
        # A sandboxed iframe without allow-same-origin presents the opaque origin
        # "null" and is treated as cross-origin by the browser, so the normal
        # same-host / allowlist comparison can never succeed. Accept it only
        # under the explicit opt-in, and only in no-login mode. The CSRF token
        # check below still runs, and real cross-site origins are still rejected.
        opaque = origin == "null" and bool(settings.allow_opaque_origin and settings.auth_disabled)
        if opaque:
            request.state.opaque_origin = True
        elif origin:
            parsed = urlsplit(origin)
            same_host = parsed.hostname == request.url.hostname
            if not same_host and origin.rstrip("/") not in settings.origins:
                return JSONResponse({"error": {"code": "origin_rejected", "message": "Cross-origin request rejected."}}, status_code=403)
        elif request.url.path.startswith("/api/"):
            return JSONResponse({"error": {"code": "origin_required", "message": "A same-origin browser request is required."}}, status_code=403)
        if request.url.path.startswith("/api/") and request.url.path != "/api/auth/login":
            supplied = request.headers.get("x-csrf-token", "")
            # Dependencies run after middleware; resolve the session token here.
            # Use the same helper as current_session so the two can never drift
            # (cookie first, opt-in X-Session-Token fallback for cookie-less hosts).
            from app.core.database import SessionLocal
            from app.security.auth import token_hash, session_token
            from app.models import Session
            with SessionLocal() as db:
                token = session_token(request)
                row = db.get(Session, token_hash(token)) if token else None
                expected = row.csrf_token if row and not row.revoked else ""
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                return JSONResponse({"error": {"code": "csrf_failed", "message": "Security token missing or invalid. Refresh and sign in again."}}, status_code=403)
        elif request.url.path == "/api/auth/login":
            cookie = request.cookies.get("omnifix_csrf", "")
            supplied = request.headers.get("x-csrf-token", "")
            if not cookie or not supplied or not secrets.compare_digest(cookie, supplied):
                return JSONResponse({"error": {"code": "csrf_failed", "message": "Refresh the sign-in page and try again."}}, status_code=403)
        length = request.headers.get("content-length", "0")
        limit = settings.max_upload_mb * 1024 * 1024 if request.url.path.endswith(("/upload", "/files")) else 1024 * 1024
        if length.isdigit() and int(length) > limit:
            return JSONResponse({"error": {"code": "request_too_large", "message": "Request exceeds the configured size limit."}}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    response.headers["X-Frame-Options"] = "DENY" if settings.environment == "production" else "SAMEORIGIN"
    frame = "'none'" if settings.environment == "production" else "*"
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors {frame}"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(AppError)
def app_error(request: Request, exc: AppError):
    return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)


@app.exception_handler(Exception)
def unexpected_error(request: Request, exc: Exception):
    log.error("Unhandled %s on %s", type(exc).__name__, request.url.path)
    return JSONResponse({"error": {"code": "internal_error", "message": "The request could not be completed safely."}}, status_code=500)


@app.get("/api/health")
def health():
    return {"status": "ok", "private": True, "registration": False, "auth_disabled": settings.auth_disabled}


for router in [auth.router, documents.router, pages.router, jobs.router, exports.router, settings_api.router, security.router, dashboard.router]:
    app.include_router(router, prefix="/api")


@app.get("/{path:path}", include_in_schema=False)
def shell(path: str):
    if path.startswith("api/"):
        return JSONResponse({"error": {"code": "not_found", "message": "Endpoint not found."}}, status_code=404)
    root = settings.frontend_dir.resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
    if candidate.is_file():
        return FileResponse(candidate, headers={"Cache-Control": "no-cache" if candidate.suffix in {".html", ".js"} else "public, max-age=31536000, immutable"})
    index = candidate / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    if root.joinpath("index.html").is_file() and path in {"dashboard", "scan", "documents", "document", "history", "export", "settings", "security", "about"}:
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": {"code": "not_found", "message": "Frontend build not found. Run npm run build in frontend/."}}, status_code=404)
