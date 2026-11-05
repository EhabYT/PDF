from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User, Document, ProcessingJob, now
from app.security.auth import current_user
from app.services.serializers import job_dict

router = APIRouter(prefix="/jobs", tags=["Processing"])


def owned_job(db, user, job_id):
    job = db.scalar(select(ProcessingJob).join(Document).where(ProcessingJob.id == job_id, Document.owner_id == user.id))
    if not job:
        raise AppError("not_found", "Job not found.", 404)
    return job


@router.get("")
def history(status: str = "", page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(ProcessingJob).join(Document).where(Document.owner_id == user.id)
    if status:
        query = query.where(ProcessingJob.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    jobs = db.scalars(query.order_by(ProcessingJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [job_dict(db, j) for j in jobs], "total": total, "page": page, "page_size": page_size}


@router.get("/{job_id}")
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return job_dict(db, owned_job(db, user, job_id))


@router.post("/{job_id}/cancel")
def cancel(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = owned_job(db, user, job_id)
    if job.status not in {"queued", "running"}:
        raise AppError("not_cancellable", "Only queued or running jobs can be cancelled.", 409)
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.completed_at = now()
    db.commit()
    return job_dict(db, job)


@router.post("/{job_id}/retry", status_code=202)
def retry(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = owned_job(db, user, job_id)
    if job.status not in {"failed", "cancelled"}:
        raise AppError("not_retryable", "Only failed or cancelled jobs can be retried.", 409)
    if job.attempts >= 3:
        raise AppError("retry_limit", "This job has reached its retry limit. Start a new processing job after reviewing the document.", 409)
    active = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == job.document_id, ProcessingJob.status.in_(["queued", "running"])))
    if active:
        raise AppError("job_active", "Another job is already active.", 409)
    job.status, job.progress, job.completed_pages, job.current_page = "queued", 0, 0, 0
    job.error_message, job.cancel_requested, job.completed_at, job.lease_until = "", False, None, None
    db.commit()
    return job_dict(db, job)
