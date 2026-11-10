import os
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="omnifix-test-"))
os.environ.update(DATA_DIR=str(TEST_DIR), SESSION_SECRET="test-secret-" + "x" * 40, ENVIRONMENT="development", TRUSTED_HOSTS="testserver,localhost,127.0.0.1", COOKIE_SECURE="false", OCR_LANGUAGES="deu+eng", AUTH_DISABLED="false", COOKIE_SAMESITE="strict", COOKIE_FALLBACK_HEADER="false", ALLOW_OPAQUE_ORIGIN="false")
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import engine, Base, SessionLocal
from app.models import User
from app.security.auth import hash_password

PASSWORD = "Test-Owner-Password-2026!"


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for folder in ["originals", "processed", "thumbnails", "temporary", "exports", "analysis"]:
        root = TEST_DIR / folder
        if root.exists():
            import shutil
            shutil.rmtree(root)
        root.mkdir(parents=True)
    with SessionLocal() as db:
        db.add(User(username="owner", password_hash=hash_password(PASSWORD)))
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app, base_url="http://testserver", headers={"Origin": "http://testserver"}) as c:
        yield c


@pytest.fixture
def auth(client):
    session = client.get("/api/auth/session").json()
    response = client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD}, headers={"X-CSRF-Token": session["csrf_token"]})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def image_bytes(text="Invoice Test Company GmbH\n12.03.2026", size=(700, 900), color=(248, 247, 242)):
    from PIL import Image, ImageDraw, ImageFont
    import io
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    draw.text((55, 70), text, fill=(35, 35, 35), font=font)
    draw.line((55, 160, 620, 160), fill=(100, 100, 100), width=2)
    draw.rectangle((450, 650, 610, 760), outline=(170, 45, 60), width=4)
    draw.text((470, 690), "STAMP", fill=(170, 45, 60), font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client, data=None, name="test.png", combine=True):
    return client.post("/api/documents/upload", files=[("files", (name, data or image_bytes(), "image/png"))], data={"combine": str(combine).lower()})


def run_document(client, doc_id):
    from app.workers.runner import claim, run_job
    for _ in range(20):
        job_id = claim()
        if not job_id:
            break
        run_job(job_id)
    return client.get(f"/api/documents/{doc_id}").json()
