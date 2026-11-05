from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Export, Document, ProcessingJob, Page, now
from app.services.storage import remove_file
from app.services.settings import get_settings


def cleanup(db: Session, owner_id: str, include_documents: bool = False) -> dict:
    prefs = get_settings(db, owner_id)
    removed = {"temporary_files": 0, "exports": 0, "documents": 0}
    cutoff = now() - timedelta(hours=prefs["temporary_retention_hours"])
    for path in (settings.storage / "temporary").rglob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff.timestamp():
            path.unlink(missing_ok=True)
            removed["temporary_files"] += 1
    for path in (settings.storage / "temporary").glob("*"):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    referenced = {p.processed_path for p in db.scalars(select(Page)).all()} | {p.thumbnail_path for p in db.scalars(select(Page)).all()} | {p.ocr_path for p in db.scalars(select(Page)).all()}
    for folder in ["processed/images", "thumbnails", "analysis"]:
        for path in (settings.storage / folder).glob("*"):
            rel = str(path.relative_to(settings.storage))
            if path.is_file() and rel not in referenced and path.stat().st_mtime < cutoff.timestamp():
                path.unlink(missing_ok=True)
                removed["temporary_files"] += 1
    exports = db.scalars(select(Export).join(Document).where(Document.owner_id == owner_id, Export.expires_at < now())).all()
    for item in exports:
        remove_file(item.path)
        db.delete(item)
        removed["exports"] += 1
    if include_documents and prefs["document_retention_days"] > 0:
        cutoff = now() - timedelta(days=prefs["document_retention_days"])
        docs = db.scalars(select(Document).where(Document.owner_id == owner_id, Document.created_at < cutoff)).all()
        for doc in docs:
            active = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(["queued", "running"])))
            if active:
                continue
            paths = [s.path for s in doc.sources] + [p.original_path for p in doc.pages] + [p.processed_path for p in doc.pages] + [p.thumbnail_path for p in doc.pages] + [p.ocr_path for p in doc.pages] + [e.path for e in doc.exports]
            db.delete(doc)
            db.flush()
            for path in paths:
                remove_file(path)
            removed["documents"] += 1
    db.commit()
    return removed
