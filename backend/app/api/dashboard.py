from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import User, Document, Page, ProcessingJob
from app.security.auth import current_user
from app.services.serializers import document_dict, job_dict
from app.services.storage import usage

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.owner_id == user.id)).all()
    page_count = db.scalar(select(func.count(Page.id)).join(Document).where(Document.owner_id == user.id))
    jobs = db.scalars(select(ProcessingJob).join(Document).where(Document.owner_id == user.id).order_by(ProcessingJob.created_at.desc()).limit(6)).all()
    recent = sorted(docs, key=lambda d: d.created_at, reverse=True)[:6]
    return {"total_documents": len(docs), "total_pages": page_count, "completed_documents": sum(bool(d.pages) and all(p.processing_status == "completed" for p in d.pages) for d in docs), "active_jobs": sum(j.status in {"queued", "running"} for j in jobs), "storage": usage(), "recent_documents": [document_dict(db, d) for d in recent], "recent_jobs": [job_dict(db, j) for j in jobs]}
