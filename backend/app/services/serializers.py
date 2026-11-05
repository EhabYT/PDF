from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Document, Page, ProcessingJob, Export, SourceFile
from .storage import resolve


def iso(value):
    return value.isoformat() + "Z" if value else None


def status(db: Session, doc: Document) -> str:
    active = db.scalars(select(ProcessingJob).where(ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(["queued", "running"]))).first()
    if active:
        return "processing" if active.status == "running" else "queued"
    pages = doc.pages
    if pages and all(p.processing_status == "completed" for p in pages):
        return "completed"
    if any(p.processing_status == "failed" for p in pages):
        return "failed"
    if any(p.processing_status == "completed" for p in pages):
        return "partial"
    return "uploaded"


def page_dict(page: Page) -> dict:
    return {"id": page.id, "document_id": page.document_id, "ordinal": page.ordinal, "width": page.width, "height": page.height, "rotation": page.rotation, "included": page.included, "status": page.processing_status, "error": page.error_message, "corners": page.corners, "detection": page.detection, "metadata": page.metadata_json, "original_url": f"/api/pages/{page.id}/file?kind=original", "processed_url": f"/api/pages/{page.id}/file?kind=processed" if page.processed_path else None, "thumbnail_url": f"/api/pages/{page.id}/file?kind=thumbnail" if page.thumbnail_path else None, "source_filename": page.source.filename}


def document_dict(db: Session, doc: Document, detail: bool = False) -> dict:
    thumb = next((p for p in doc.pages if p.included and p.thumbnail_path), next((p for p in doc.pages if p.thumbnail_path), None))
    size = sum(s.size for s in doc.sources)
    size += sum(resolve(p.processed_path).stat().st_size for p in doc.pages if p.processed_path and resolve(p.processed_path).exists())
    data = {"id": doc.id, "name": doc.name, "original_filename": doc.original_filename, "document_type": doc.document_type, "category": doc.category, "detected_type": doc.detected_type, "organization": doc.organization, "subject": doc.subject, "detected_date": doc.detected_date, "date_source": doc.date_source, "description": doc.description, "suggested_name": doc.suggested_name, "approved_name": doc.approved_name, "naming_status": doc.naming_status, "name_edited": doc.name_edited, "created_at": iso(doc.created_at), "updated_at": iso(doc.updated_at), "page_count": len(doc.pages), "included_count": sum(p.included for p in doc.pages), "status": status(db, doc), "size_bytes": size, "thumbnail_url": f"/api/pages/{thumb.id}/file?kind=thumbnail" if thumb else None}
    if detail:
        data["pages"] = [page_dict(p) for p in doc.pages]
        data["sources"] = [{"id": s.id, "filename": s.filename, "size": s.size, "mime": s.mime, "checksum": s.checksum} for s in doc.sources]
        active = db.scalars(select(ProcessingJob).where(ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(["queued", "running"])).order_by(ProcessingJob.created_at.desc())).first()
        data["active_job"] = job_dict(db, active) if active else None
    return data


def job_dict(db: Session, job: ProcessingJob) -> dict:
    doc = db.get(Document, job.document_id)
    return {"id": job.id, "document_id": job.document_id, "document_name": doc.name if doc else "Deleted document", "page_id": job.page_id, "kind": job.kind, "status": job.status, "progress": job.progress, "total_pages": job.total_pages, "completed_pages": job.completed_pages, "current_page": job.current_page, "error": job.error_message, "attempts": job.attempts, "created_at": iso(job.created_at), "started_at": iso(job.started_at), "completed_at": iso(job.completed_at)}


def export_dict(item: Export) -> dict:
    return {"id": item.id, "document_id": item.document_id, "filename": item.filename, "format": item.format, "size_bytes": item.size, "checksum": item.checksum, "page_count": len(item.page_ids), "created_at": iso(item.created_at), "expires_at": iso(item.expires_at), "download_url": f"/api/exports/{item.id}/download"}
