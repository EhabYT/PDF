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
