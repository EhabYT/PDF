import io
import zipfile
import fitz
from pathlib import Path
from app.core.database import SessionLocal
from app.models import Page, SourceFile, ProcessingJob
from app.services.storage import resolve
from processing.omnifix.preservation import checksum
from tests.conftest import image_bytes, upload, run_document


def test_upload_process_preserves_original_and_deterministic(auth):
    original = image_bytes()
    response = upload(auth, original)
    assert response.status_code == 202, response.text
    doc_id = response.json()["documents"][0]["id"]
    with SessionLocal() as db:
        source = db.query(SourceFile).first()
        path = resolve(source.path)
        assert path.read_bytes() == original
        assert checksum(path) == source.checksum
    doc = run_document(auth, doc_id)
    assert doc["status"] == "completed"
    page = doc["pages"][0]
    assert page["processed_url"] and page["thumbnail_url"]
    with SessionLocal() as db:
        source = db.query(SourceFile).first()
        assert resolve(source.path).read_bytes() == original
        processed = resolve(db.query(Page).first().processed_path).read_bytes()
    first = page["metadata"]["processed_checksum"]
    assert auth.post(f"/api/pages/{page['id']}/reprocess").status_code == 202
    doc = run_document(auth, doc_id)
    assert doc["pages"][0]["metadata"]["processed_checksum"] == first
    assert auth.get(page["processed_url"]).status_code == 200
    assert auth.get(page["original_url"]).content == original


def test_multipage_order_rotation_include_and_corners(auth):
    files = [("files", (f"p{i}.png", image_bytes(f"Page {i}"), "image/png")) for i in range(3)]
    response = auth.post("/api/documents/upload", files=files, data={"combine": "true"})
    doc_id = response.json()["documents"][0]["id"]
    doc = run_document(auth, doc_id)
    ids = [p["id"] for p in doc["pages"]]
    assert auth.patch(f"/api/pages/{ids[0]}/order", json={"order": list(reversed(ids))}).status_code == 200
    assert auth.patch(f"/api/pages/{ids[0]}/rotation", json={"rotation": 90}).status_code == 200
    run_document(auth, doc_id)
    assert auth.patch(f"/api/pages/{ids[1]}/include", json={"included": False}).status_code == 200
    corners = [[.1, .1], [.9, .12], [.88, .9], [.12, .88]]
    assert auth.patch(f"/api/pages/{ids[2]}/corners", json={"corners": corners, "apply": True}).status_code == 202
    doc = run_document(auth, doc_id)
    assert doc["included_count"] == 2
    assert auth.patch(f"/api/pages/{ids[2]}/corners", json={"corners": [[0, 0], [1, 1], [0, 1], [1, 0]]}).status_code == 400
    with SessionLocal() as db:
        assert db.query(SourceFile).count() == 3  # excluding a page never deletes its source


def test_pdf_import_and_export_page_count(auth):
    import img2pdf
    pdf = img2pdf.convert([image_bytes("Page one"), image_bytes("Page two")])
    response = upload(auth, pdf, "source.pdf")
    assert response.status_code == 202, response.text
    doc_id = response.json()["documents"][0]["id"]
    doc = run_document(auth, doc_id)
    assert doc["page_count"] == 2 and doc["status"] == "completed"
    with SessionLocal() as db:
        source = db.query(SourceFile).first()
        assert resolve(source.path).read_bytes() == pdf
    export = auth.post(f"/api/documents/{doc_id}/export/pdf", json={"page_size": "a4", "orientation": "portrait", "quality": 95})
    assert export.status_code == 202
    run_document(auth, doc_id)
    items = auth.get(f"/api/documents/{doc_id}/exports").json()["items"]
    assert len(items) == 1
    downloaded = auth.get(items[0]["download_url"])
    assert downloaded.status_code == 200
    with fitz.open(stream=downloaded.content, filetype="pdf") as output:
        assert len(output) == 2
        assert abs(output[0].rect.width - 595.276) < 1


def test_zip_exports_and_originals(auth):
    doc_id = upload(auth).json()["documents"][0]["id"]
    run_document(auth, doc_id)
    for fmt in ["images", "zip", "originals"]:
        assert auth.post(f"/api/documents/{doc_id}/export/{fmt}", json={}).status_code == 202
        run_document(auth, doc_id)
    items = auth.get(f"/api/documents/{doc_id}/exports").json()["items"]
    assert len(items) == 3
    for item in items:
        response = auth.get(item["download_url"])
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            if item["format"] == "originals":
                assert archive.read(archive.namelist()[0]) == image_bytes()


def test_smart_naming_and_manual_override(auth):
    doc_id = upload(auth, image_bytes("Mietvertrag\nStadt Essen\n12.03.2026"), "IMG_5821.jpg" if False else "IMG_5821.png").json()["documents"][0]["id"]
    doc = run_document(auth, doc_id)
    assert doc["suggested_name"].endswith(".pdf")
    assert "Mietvertrag" in doc["suggested_name"]
    assert doc["original_filename"] == "IMG_5821.png"
    assert auth.patch(f"/api/documents/{doc_id}", json={"name": "My_Rental_Agreement", "category": "Rental Agreements"}).status_code == 200
    assert auth.get(f"/api/documents/{doc_id}").json()["name"] == "My_Rental_Agreement"


def test_job_cancel_retry_and_history(auth):
    doc_id = upload(auth).json()["documents"][0]["id"]
    job = auth.get("/api/jobs").json()["items"][0]
    assert auth.post(f"/api/jobs/{job['id']}/cancel").status_code == 200
    assert auth.post(f"/api/jobs/{job['id']}/retry").status_code == 202
    doc = run_document(auth, doc_id)
    assert doc["status"] == "completed"
    assert len(auth.get("/api/jobs").json()["items"]) == 1


def test_delete_removes_private_files(auth):
    doc_id = upload(auth).json()["documents"][0]["id"]
    run_document(auth, doc_id)
    with SessionLocal() as db:
        paths = [resolve(s.path) for s in db.query(SourceFile).all()] + [resolve(p.processed_path) for p in db.query(Page).all()]
    assert auth.delete(f"/api/documents/{doc_id}").status_code == 200
    assert all(not p.exists() for p in paths)
    assert auth.get(f"/api/documents/{doc_id}").status_code == 404


def test_settings_validation_and_dashboard(auth):
    assert auth.patch("/api/settings", json={"intensity": 2}).status_code == 400
    assert auth.patch("/api/settings", json={"theme": "invalid"}).status_code == 400
    assert auth.patch("/api/settings", json={"intensity": .7, "filename_language": "de"}).status_code == 200
    upload(auth)
    data = auth.get("/api/dashboard").json()
    assert data["total_documents"] == 1 and data["total_pages"] == 1
    assert data["storage"]["total_bytes"] > 0
