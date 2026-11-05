from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Document, ProcessingJob, Page
from app.core.errors import AppError
from .settings import get_settings


def enqueue(db: Session, doc: Document, kind: str = "process", page_id: str | None = None) -> ProcessingJob:
    active = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(["queued", "running"])))
    if active:
        raise AppError("job_active", "This document already has an active job.", 409)
    pages = [p for p in doc.pages if (p.id == page_id if page_id else p.included)]
    if not pages:
        raise AppError("no_pages", "Select at least one page to process.", 400)
    owner = doc.owner_id
    prefs = get_settings(db, owner)
    job = ProcessingJob(document_id=doc.id, page_id=page_id, kind=kind, total_pages=len(pages), settings_snapshot=prefs)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
