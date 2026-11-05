from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User, Document, Export, ProcessingJob, now
from app.schemas import ExportRequest
from app.security.auth import current_user
from app.api.documents import owned_document
from app.services.jobs import enqueue
from app.services.settings import get_settings
from app.services.serializers import job_dict, export_dict
from app.services.storage import resolve
from processing.omnifix.naming import safe_filename
from processing.omnifix.preservation import verify_original

router = APIRouter(tags=["Exports"])


@router.post("/documents/{document_id}/export/{format}", status_code=202)
def create_export(document_id: str, format: str, body: ExportRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if format not in {"pdf", "images", "zip", "originals"}:
        raise AppError("invalid_format", "Choose PDF, images, complete ZIP or originals ZIP.", 404)
    doc = owned_document(db, user, document_id)
    selected = [p for p in doc.pages if p.included and (not body.page_ids or p.id in body.page_ids)]
    if body.page_ids and (len(set(body.page_ids)) != len(body.page_ids) or len(selected) != len(body.page_ids)):
        raise AppError("invalid_pages", "Export selection contains missing, duplicate or excluded pages.")
    if not selected:
        raise AppError("no_pages", "Select at least one page.")
    prefs = get_settings(db, user.id)
    filename = safe_filename(body.filename or doc.approved_name or doc.suggested_name or doc.name, "", prefs["transliterate"])
    if body.filename:
        doc.approved_name, doc.name, doc.naming_status, doc.name_edited = filename, filename, "reviewed", True
    job = enqueue(db, doc, kind=f"export_{format}")
    job.settings_snapshot = {**prefs, **body.model_dump(), "filename": filename, "page_ids": [p.id for p in selected]}
    job.total_pages = len(selected)
    db.commit()
    return job_dict(db, job)


@router.get("/documents/{document_id}/exports")
def document_exports(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    items = db.scalars(select(Export).where(Export.document_id == doc.id).order_by(Export.created_at.desc())).all()
    return {"items": [export_dict(e) for e in items]}


@router.get("/exports/{export_id}/download")
def download(export_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(Export).join(Document).where(Export.id == export_id, Document.owner_id == user.id))
    if not item:
        raise AppError("not_found", "Export not found.", 404)
    if item.expires_at < now():
        raise AppError("export_expired", "This export has expired. Create a new export.", 410)
    path = resolve(item.path)
    if not path.is_file():
        raise AppError("not_found", "Export file not found.", 404)
    verify_original(path, item.checksum)
    return FileResponse(path, media_type="application/pdf" if item.format == "pdf" else "application/zip", filename=item.filename, headers={"Cache-Control": "private, no-store", "Content-Security-Policy": "default-src 'none'; sandbox"})
