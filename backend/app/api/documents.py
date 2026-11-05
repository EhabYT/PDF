from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User, Document, ProcessingJob, SourceFile
from app.schemas import DocumentPatch
from app.security.auth import current_user
from app.services.uploads import receive_uploads
from app.services.serializers import document_dict, job_dict
from app.services.storage import resolve, remove_file
from app.services.jobs import enqueue
from app.services.settings import get_settings
from app.models import ProcessingJob
from processing.omnifix.naming import CATEGORIES, safe_filename
from processing.omnifix.preservation import verify_original

router = APIRouter(prefix="/documents", tags=["Documents"])


def owned_document(db: Session, user: User, document_id: str) -> Document:
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise AppError("not_found", "Document not found.", 404)
    return doc


@router.post("/upload", status_code=202)
async def upload(files: list[UploadFile] = File(...), combine: bool = Form(True), user: User = Depends(current_user), db: Session = Depends(get_db)):
    docs = await receive_uploads(files, combine, user, db)
    return {"documents": [document_dict(db, d) for d in docs]}


@router.get("")
def list_documents(q: str = "", category: str = "", sort: str = "newest", date_from: str = "", date_to: str = "", page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Document).where(Document.owner_id == user.id)
    if q:
        query = query.where(or_(Document.name.ilike(f"%{q}%"), Document.original_filename.ilike(f"%{q}%"), Document.organization.ilike(f"%{q}%")))
    if category:
        query = query.where(Document.category == category)
    try:
        if date_from:
            query = query.where(Document.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.where(Document.created_at < datetime.fromisoformat(date_to))
    except ValueError:
        raise AppError("invalid_date", "Use YYYY-MM-DD date filters.")
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = {"oldest": Document.created_at.asc(), "name": Document.name.asc(), "pages": Document.created_at.desc()}.get(sort, Document.created_at.desc())
    docs = db.scalars(query.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [document_dict(db, d) for d in docs], "total": total, "page": page, "page_size": page_size}


@router.get("/{document_id}")
def get_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return document_dict(db, owned_document(db, user, document_id), True)


@router.patch("/{document_id}")
def patch_document(document_id: str, body: DocumentPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    if body.name is not None:
        doc.name = safe_filename(body.name, "", False).removesuffix(".")
        doc.name_edited = True
    if body.category is not None:
        if body.category not in CATEGORIES:
            raise AppError("invalid_category", "Choose a supported document category.")
        doc.category, doc.name_edited = body.category, True
    if body.accept_name:
        doc.approved_name = safe_filename(body.name or doc.suggested_name or doc.name, "", False)
        doc.name = doc.approved_name
        doc.naming_status = "reviewed"
    if body.filename_language or body.transliterate is not None:
        from processing.omnifix.naming import classify
        prefs = get_settings(db, user.id)
        texts = [resolve(p.ocr_path).read_text(encoding="utf-8") for p in doc.pages if p.ocr_path]
        result = classify(texts, doc.created_at.year, body.filename_language or prefs["filename_language"], body.transliterate if body.transliterate is not None else prefs["transliterate"])
        doc.suggested_name = result["name"]
        if not doc.name_edited:
            doc.name = result["name"].removesuffix(".pdf")
    db.commit()
    return document_dict(db, doc)


@router.delete("/{document_id}")
def delete_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    active = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(["queued", "running"])))
    if active:
        raise AppError("job_active", "Cancel or finish the active job before deleting this document.", 409)
    paths = [s.path for s in doc.sources] + [p.original_path for p in doc.pages] + [p.processed_path for p in doc.pages] + [p.thumbnail_path for p in doc.pages] + [p.ocr_path for p in doc.pages] + [e.path for e in doc.exports]
    db.delete(doc)
    db.commit()
    for path in paths:
        remove_file(path)
    return {"ok": True}


@router.post("/{document_id}/files", status_code=202)
async def add_files(document_id: str, files: list[UploadFile] = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    docs = await receive_uploads(files, True, user, db, target=doc)
    return document_dict(db, docs[0], True)


@router.post("/{document_id}/process", status_code=202)
def process(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    if not get_settings(db, user.id)["processing_enabled"]:
        raise AppError("processing_disabled", "Enable OmniFix processing in Settings first.", 409)
    return job_dict(db, enqueue(db, doc))


@router.get("/{document_id}/sources/{source_id}/download")
def download_source(document_id: str, source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = owned_document(db, user, document_id)
    source = db.scalar(select(SourceFile).where(SourceFile.id == source_id, SourceFile.document_id == doc.id))
    if not source:
        raise AppError("not_found", "Source file not found.", 404)
    path = resolve(source.path)
    verify_original(path, source.checksum)
    return FileResponse(path, media_type=source.mime, filename=source.filename, headers={"Cache-Control": "private, no-store", "Content-Security-Policy": "default-src 'none'; sandbox"})
