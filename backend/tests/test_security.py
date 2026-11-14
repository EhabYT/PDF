import io
from datetime import timedelta
from app.core.database import SessionLocal
from app.models import User, Session, Document, now
from app.security.auth import hash_password, token_hash
from tests.conftest import PASSWORD, image_bytes, upload


def test_public_registration_disabled(client):
    assert client.post("/api/auth/register", json={}).status_code in {403, 404, 405}
    assert client.get("/api/health").json()["registration"] is False


def test_login_and_session_flow(client):
    info = client.get("/api/auth/session").json()
    assert info["authenticated"] is False
    assert client.post("/api/auth/login", json={"username": "owner", "password": "wrong"}, headers={"X-CSRF-Token": info["csrf_token"]}).status_code == 401
    response = client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD}, headers={"X-CSRF-Token": info["csrf_token"]})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/session").json()["authenticated"] is True
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/documents").status_code == 401


def test_protected_endpoints_fail_closed(client):
    for path in ["/api/documents", "/api/dashboard", "/api/settings", "/api/security/sessions", "/api/jobs", "/api/pages/unknown/file", "/api/exports/unknown/download"]:
        assert client.get(path).status_code == 401, path


def test_csrf_required(auth):
    response = auth.post("/api/settings", json={"theme": "dark"}, headers={"X-CSRF-Token": ""})
    assert response.status_code == 403
    assert auth.patch("/api/settings", json={"theme": "dark"}).status_code == 200


def test_cross_origin_rejected(auth):
    assert auth.patch("/api/settings", json={"theme": "dark"}, headers={"Origin": "https://evil.example"}).status_code == 403


def test_session_expiration_and_revocation(auth):
    with SessionLocal() as db:
        row = db.query(Session).first()
        row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert auth.get("/api/documents").status_code == 401


def test_login_rate_limit(client):
    info = client.get("/api/auth/session").json()
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "owner", "password": "bad"}, headers={"X-CSRF-Token": info["csrf_token"]})
    response = client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD}, headers={"X-CSRF-Token": info["csrf_token"]})
    assert response.status_code == 429


def test_idor_document_and_file_access(auth):
    with SessionLocal() as db:
        other = User(username="other", password_hash=hash_password(PASSWORD))
        db.add(other)
        db.flush()
        doc = Document(owner_id=other.id, name="Private", original_filename="x.png")
        db.add(doc)
        db.commit()
        doc_id = doc.id
    assert auth.get(f"/api/documents/{doc_id}").status_code == 404
    assert auth.delete(f"/api/documents/{doc_id}").status_code == 404
    assert auth.post(f"/api/documents/{doc_id}/process").status_code == 404


def test_malicious_upload_signature(auth):
    response = upload(auth, b"%PDF-1.4\nnot really an image", "fake.png")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_signature"


def test_unsupported_upload(auth):
    assert upload(auth, b"<svg></svg>", "x.svg").status_code == 400


def test_corrupt_image(auth):
    assert upload(auth, b"\x89PNG\r\n\x1a\ncorrupt", "x.png").status_code == 400


def test_oversized_upload(auth, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_file_mb", 1)
    assert upload(auth, image_bytes() + b"x" * (1024 * 1024), "big.png").status_code == 400


def test_total_request_size_limit(auth, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_file_mb", 10)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = upload(auth, image_bytes() + b"x" * (1024 * 1024), "big.png")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_batch_page_limit(auth, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_pages", 2)
    files = [("files", (f"page-{i}.png", image_bytes(), "image/png")) for i in range(3)]
    response = auth.post("/api/documents/upload", files=files, data={"combine": "true"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"invalid_upload", "too_many_pages"}


def test_invalid_pdf(auth):
    assert upload(auth, b"%PDF-1.7\nbroken", "broken.pdf").status_code == 400


def test_path_traversal_rejected(auth):
    assert auth.get("/api/pages/../../etc/passwd/file").status_code in {401, 404}
    r = upload(auth)
    page_id = r.json()["documents"][0]["id"]
    assert auth.get(f"/api/pages/{page_id}/file?kind=../../etc/passwd").status_code in {400, 404}
    assert auth.get("/api/exports/..%2f..%2fetc%2fpasswd/download").status_code == 404


def test_password_change_invalidates_other_sessions(auth, client):
    assert auth.post("/api/auth/password/change", json={"current_password": "wrong", "new_password": "New-Strong-Password-2026!"}).status_code == 403
    assert auth.post("/api/auth/password/change", json={"current_password": PASSWORD, "new_password": "New-Strong-Password-2026!"}).status_code == 200
    with SessionLocal() as db:
        assert db.query(User).first().password_hash.startswith("$argon2id$")


def test_totp_enable_and_login(client, auth):
    import pyotp
    setup = auth.post("/api/auth/totp/setup").json()
    code = pyotp.TOTP(setup["secret"]).now()
    enabled = auth.post("/api/auth/totp/enable", json={"code": code, "password": PASSWORD})
    assert enabled.status_code == 200
    assert len(enabled.json()["recovery_codes"]) == 8
    auth.post("/api/auth/logout")
    info = client.get("/api/auth/session").json()
    assert client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD}, headers={"X-CSRF-Token": info["csrf_token"]}).status_code == 401
    code = pyotp.TOTP(setup["secret"]).now()
    assert client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD, "totp_code": code}, headers={"X-CSRF-Token": info["csrf_token"]}).status_code == 200


def test_security_headers_and_no_public_storage(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors" in response.headers["content-security-policy"]
    assert client.get("/storage/originals/images/anything.jpg").status_code in {401, 404}


def test_auth_disabled_auto_login(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    # No /login call: the session endpoint transparently signs in the owner.
    info = client.get("/api/auth/session").json()
    assert info["authenticated"] is True
    assert info["auth_disabled"] is True
    client.headers["X-CSRF-Token"] = info["csrf_token"]
    # Protected reads work without ever signing in.
    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/dashboard").status_code == 200
    # CSRF protection remains enabled even in no-login mode.
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"X-CSRF-Token": ""}).status_code == 403
    assert client.patch("/api/settings", json={"theme": "dark"}).status_code == 200


def test_auth_enabled_by_default_requires_login(client):
    info = client.get("/api/auth/session").json()
    assert info["authenticated"] is False
    assert info.get("auth_disabled", False) is False
    assert client.get("/api/documents").status_code == 401


def test_auth_disabled_csrf_stable_after_idle(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    info = client.get("/api/auth/session").json()
    csrf = info["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf
    # Force the auto-provisioned session to look idle-expired.
    with SessionLocal() as db:
        for s in db.query(Session).all():
            s.last_seen = now() - timedelta(minutes=settings.session_idle_minutes + 5)
        db.commit()
    # A background poll must refresh the session in place, not rotate the
    # cookie/CSRF token (regression: "Security token missing or invalid").
    assert client.get("/api/dashboard").status_code == 200
    # The original CSRF token must still be accepted for a mutating request.
    assert client.patch("/api/settings", json={"theme": "dark"}).status_code == 200


def test_cookie_samesite_policy(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "cookie_secure", False)
    # Default stays strict (most protective) for normal same-origin deployments.
    monkeypatch.setattr(settings, "cookie_samesite", "strict")
    client.cookies.clear()
    sc = client.get("/api/auth/session").headers["set-cookie"].lower()
    assert "samesite=strict" in sc
    assert settings.cookie_secure_effective is False
    # Cross-site/embedded preview opt-in: SameSite=None must force Secure,
    # otherwise browsers drop the cookie and every mutation fails CSRF.
    monkeypatch.setattr(settings, "cookie_samesite", "none")
    client.cookies.clear()
    sc = client.get("/api/auth/session").headers["set-cookie"].lower()
    assert "samesite=none" in sc and "secure" in sc
    assert settings.cookie_secure_effective is True
    # Invalid values fall back to the secure default.
    monkeypatch.setattr(settings, "cookie_samesite", "bogus")
    assert settings.cookie_samesite_effective == "strict"


def test_header_session_transport_opt_in(client, monkeypatch):
    """Cookie-less hosts (sandboxed cross-site iframe preview) must still work."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "cookie_fallback_header", True)
    info = client.get("/api/auth/session").json()
    token = info.get("session_token")
    assert token, "opt-in transport must expose the opaque session token"
    client.cookies.clear()  # simulate a browser that refuses to store cookies
    h = {"X-CSRF-Token": info["csrf_token"], "X-Session-Token": token}
    assert client.get("/api/documents", headers=h).status_code == 200
    assert client.get("/api/dashboard", headers=h).status_code == 200
    assert client.patch("/api/settings", json={"theme": "dark"}, headers=h).status_code == 200
    # CSRF is still mandatory: the header transport does not bypass it.
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"X-Session-Token": token}).status_code == 403
    client.cookies.clear()
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"X-CSRF-Token": info["csrf_token"]}).status_code == 403
    # A forged/unknown session token carries no CSRF token, so it can never
    # mutate anything (reads merely re-provision, as no-login mode intends).
    forged = {**h, "X-Session-Token": "not-a-real-token"}
    assert client.patch("/api/settings", json={"theme": "dark"}, headers=forged).status_code == 403


def test_header_transport_disabled_by_default(client, monkeypatch):
    """Default deployments must never expose the session token to JavaScript."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "cookie_fallback_header", False)
    info = client.get("/api/auth/session").json()
    assert "session_token" not in info
    # Even in no-login mode the client is never handed the token, so a browser
    # that cannot store cookies stays broken rather than silently downgrading.
    client.cookies.clear()
    assert "session_token" not in client.get("/api/auth/session").json()


def test_header_transport_requires_no_login_mode(client, monkeypatch):
    """The transport is ignored when real login is enforced."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "cookie_fallback_header", True)
    info = client.get("/api/auth/session").json()
    assert "session_token" not in info


def test_opaque_origin_opt_in(client, monkeypatch):
    """Sandboxed iframes (opaque origin "null") work only when explicitly enabled."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "cookie_fallback_header", True)
    info = client.get("/api/auth/session").json()
    token, csrf = info["session_token"], info["csrf_token"]
    h = {"Origin": "null", "X-CSRF-Token": csrf, "X-Session-Token": token}
    # Default: an opaque origin is plain cross-origin and must be rejected.
    assert client.get("/api/documents", headers=h).status_code == 200  # GET is safe
    assert client.patch("/api/settings", json={"theme": "dark"}, headers=h).status_code == 403
    # Opt in: the sandboxed embed is accepted, CSRF still enforced.
    monkeypatch.setattr(settings, "allow_opaque_origin", True)
    client.cookies.clear()
    assert client.patch("/api/settings", json={"theme": "dark"}, headers=h).status_code == 200
    assert client.get("/api/documents", headers=h).status_code == 200
    # CSRF still mandatory for the opaque origin.
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"Origin": "null", "X-Session-Token": token}).status_code == 403
    # A real foreign origin is still rejected even with the opt-in enabled.
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf, "X-Session-Token": token}).status_code == 403


def test_opaque_origin_never_allowed_with_real_login(client, monkeypatch):
    """The opaque-origin allowance must not weaken normal authenticated mode."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "allow_opaque_origin", True)
    assert client.patch("/api/settings", json={"theme": "dark"}, headers={"Origin": "null"}).status_code == 403


def test_head_requests_served_for_client_routing(client, monkeypatch):
    """Next.js sends HEAD when prefetching routes; a 405 breaks navigation."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_disabled", True)
    client.get("/api/auth/session")
    for path in ("/dashboard/", "/documents/", "/scan/", "/settings/", "/about/"):
        response = client.head(path)
        assert response.status_code == 200, f"HEAD {path} -> {response.status_code}"


def test_embedded_cors_allows_next_router_headers(monkeypatch):
    """In an embedded preview every request is preflighted; Next's RSC headers
    (including next-router-segment-prefetch) must be allowed or navigation dies."""
    from app.core.config import settings
    from app.main import cors_configuration
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "allow_opaque_origin", True)
    config = cors_configuration()
    assert "null" in config["allow_origins"]
    assert config["allow_private_network"] is True
    allowed = {h.lower() for h in config["allow_headers"]}
    for header in ("rsc", "next-router-prefetch", "next-router-segment-prefetch", "next-url", "x-csrf-token", "x-session-token"):
        assert header in allowed, f"{header} missing from {sorted(allowed)}"
    assert "HEAD" in config["allow_methods"]


def test_embedded_cors_off_by_default(monkeypatch):
    """No embedded allowances unless the no-login embed mode is explicitly on."""
    from app.core.config import settings
    from app.main import cors_configuration
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(settings, "allow_opaque_origin", False)
    config = cors_configuration()
    assert "null" not in config["allow_origins"]
    assert config["allow_private_network"] is False
    assert all("next" not in h.lower() and h.lower() != "rsc" for h in config["allow_headers"])
