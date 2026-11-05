from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User, Page, Document, ProcessingJob
from app.schemas import OrderPatch, RotationPatch, IncludePatch, CornersPatch
from app.security.auth import current_user
from app.api.documents import owned_document
from app.services.serializers import page_dict, job_dict, document_dict
from app.services.storage import resolve
from app.services.jobs import enqueue
from app.services.settings import get_settings
from processing.omnifix.geometry import valid_corners, rotate_corners
from processing.omnifix.preservation import verify_original

router = APIRouter(prefix="/pages", tags=["Pages"])


def owned_page(db: Session, user: User, page_id: str) -> Page:
    page = db.scalar(select(Page).join(Document).where(Page.id == page_id, Document.owner_id == user.id))
    if not page:
        raise AppError("not_found", "Page not found.", 404)
    return page


def ensure_idle(db, page):
    active = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == page.document_id, ProcessingJob.status.in_(["queued", "running"])))
    if active:
        raise AppError("job_active", "Wait for or cancel the active job before editing pages.", 409)


@router.get("/{page_id}/file")
def page_file(page_id: str, kind: str = "processed", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if kind not in {"original", "processed", "thumbnail"}:
        raise AppError("invalid_kind", "Invalid preview type.")
    page = owned_page(db, user, page_id)
    rel = {"original": page.original_path, "processed": page.processed_path, "thumbnail": page.thumbnail_path}[kind]
    if not rel:
        raise AppError("not_ready", "This preview is not ready yet.", 404)
    path = resolve(rel)
    if not path.is_file():
        raise AppError("not_found", "File not found.", 404)
    if kind == "original":
        verify_original(path, page.checksum)
    return FileResponse(path, media_type="image/png" if path.suffix == ".png" else "image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.patch("/{page_id}/rotation")
def rotation(page_id: str, body: RotationPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    ensure_idle(db, page)
    delta = (body.rotation - page.rotation) % 360
    page.rotation = body.rotation
    if page.corners:
        page.corners = rotate_corners(page.corners, delta)
    page.processing_status = "uploaded"
    db.commit()
    job = enqueue(db, db.get(Document, page.document_id), page_id=page.id) if get_settings(db, user.id)["processing_enabled"] else None
    return {"page": page_dict(page), "job": job_dict(db, job) if job else None}


@router.patch("/{page_id}/include")
def include(page_id: str, body: IncludePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    ensure_idle(db, page)
    page.included = body.included
    db.commit()
    return page_dict(page)


@router.patch("/{page_id}/corners", status_code=202)
def corners(page_id: str, body: CornersPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    ensure_idle(db, page)
    if len(body.corners) != 4 or any(len(p) != 2 for p in body.corners) or not valid_corners(body.corners):
        raise AppError("invalid_corners", "Choose four ordered corners inside the image with a valid document area.")
    page.corners = body.corners
    page.metadata_json = {**page.metadata_json, "manual_boundary": True}
    page.processing_status = "uploaded"
    db.commit()
    job = enqueue(db, db.get(Document, page.document_id), page_id=page.id) if body.apply else None
    return {"page": page_dict(page), "job": job_dict(db, job) if job else None}


@router.post("/{page_id}/detect", status_code=202)
def detect(page_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    ensure_idle(db, page)
    page.metadata_json = {**page.metadata_json, "manual_boundary": False}
    page.corners = None
    db.commit()
    return job_dict(db, enqueue(db, db.get(Document, page.document_id), kind="detect", page_id=page.id))


@router.post("/{page_id}/reprocess", status_code=202)
def reprocess(page_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    if not get_settings(db, user.id)["processing_enabled"]:
        raise AppError("processing_disabled", "Enable OmniFix processing in Settings first.", 409)
    return job_dict(db, enqueue(db, db.get(Document, page.document_id), page_id=page.id))


@router.patch("/{page_id}/order")
def page_order(page_id: str, body: OrderPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    page = owned_page(db, user, page_id)
    doc = owned_document(db, user, page.document_id)
    ensure_idle(db, page)
    if set(body.order) != {p.id for p in doc.pages} or len(body.order) != len(doc.pages):
        raise AppError("invalid_order", "The order must contain every page exactly once.")
    for index, pid in enumerate(body.order):
        db.get(Page, pid).ordinal = -index - 1
    db.flush()
    for index, pid in enumerate(body.order):
        db.get(Page, pid).ordinal = index
    db.commit()
    return document_dict(db, doc, True)
