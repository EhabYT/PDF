from datetime import timedelta
import logging
import os
import signal
import time
from uuid import uuid4
from sqlalchemy import select, update
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Document, Page, ProcessingJob, User, now
from app.services.storage import resolve, new_path, remove_file
from app.services.settings import get_settings
from app.services.exporter import run_export
from app.services.cleanup import cleanup
from processing.omnifix.pipeline import process_file, thumbnail, read_oriented, rotate
from processing.omnifix.detector import detect_document
from processing.omnifix.ocr import recognize
from processing.omnifix.naming import classify
from processing.omnifix.preservation import verify_original

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("omnifix.worker")
stop = False


def handle_stop(signum, frame):
    global stop
    stop = True


class PageTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise PageTimeout("Processing time limit reached")


def recover_stale():
    with SessionLocal() as db:
        stale = db.scalars(select(ProcessingJob).where(ProcessingJob.status == "running", ProcessingJob.lease_until < now())).all()
        for job in stale:
            job.status = "queued"
            job.lease_until = None
            for page in db.scalars(select(Page).where(Page.document_id == job.document_id, Page.processing_status == "processing")):
                page.processing_status = "uploaded"
        db.commit()


def claim():
    with SessionLocal() as db:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.status == "queued").order_by(ProcessingJob.created_at).limit(1))
        if not job:
            return None
        result = db.execute(update(ProcessingJob).where(ProcessingJob.id == job.id, ProcessingJob.status == "queued").values(status="running", started_at=now(), attempts=ProcessingJob.attempts + 1, lease_until=now() + timedelta(minutes=5)))
        db.commit()
        return job.id if result.rowcount else None


def finish_cancel(db, job):
    for page in db.scalars(select(Page).where(Page.document_id == job.document_id, Page.processing_status == "processing")):
        page.processing_status = "uploaded"
    job.status = "cancelled"
    job.completed_at = now()
    job.error_message = "Cancelled safely at a page boundary."
    db.commit()


def run_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if not job or job.status != "running":
            return
        doc = db.get(Document, job.document_id)
        if not doc:
            job.status = "failed"
            job.error_message = "Document no longer exists."
            job.completed_at = now()
            db.commit()
            return
        try:
            if job.cancel_requested:
                finish_cancel(db, job)
                return
            if job.kind.startswith("export_"):
                run_export(db, job)
                return
            pages = [p for p in doc.pages if (p.id == job.page_id if job.page_id else p.included)]
            job.total_pages = len(pages)
            failed = 0
            for index, page in enumerate(pages):
                db.refresh(job)
                if job.cancel_requested or stop:
                    finish_cancel(db, job)
                    return
                job.current_page = index + 1
                job.lease_until = now() + timedelta(minutes=5)
                page.processing_status = "processing"
                db.commit()
                old_processed, old_thumb, old_ocr = page.processed_path, page.thumbnail_path, page.ocr_path
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, settings.page_timeout_seconds)
                try:
                    source = resolve(page.original_path)
                    verify_original(source, page.checksum)
                    verify_original(resolve(page.source.path), page.source.checksum)
                    if job.kind == "detect":
                        rgb = rotate(read_oriented(source, settings.max_pixels), page.rotation)
                        page.detection = detect_document(rgb, True)
                        page.corners = page.detection["corners"]
                        page.processing_status = "completed" if page.processed_path else "uploaded"
                    else:
                        rel, output = new_path("processed/images", ".jpg")
                        options = {**job.settings_snapshot, "max_output_pixels": min(job.settings_snapshot.get("max_output_pixels", 24000000), settings.max_output_pixels)}
                        metadata = process_file(source, output, page.checksum, options, page.corners, bool(page.metadata_json.get("manual_boundary")), page.rotation, settings.max_pixels)
                        thumb_rel, thumb_path = new_path("thumbnails", ".jpg")
                        thumbnail(output, thumb_path)
                        text, ocr_meta = recognize(output, settings.tesseract_cmd, settings.ocr_languages, settings.ocr_timeout_seconds)
                        ocr_rel, ocr_path = new_path("analysis", ".txt")
                        ocr_path.write_text(text, encoding="utf-8")
                        page.processed_path, page.thumbnail_path, page.ocr_path = rel, thumb_rel, ocr_rel
                        page.width, page.height = metadata["output_shape"][1], metadata["output_shape"][0]
                        page.detection = metadata
                        page.metadata_json = {**metadata, "ocr": ocr_meta}
                        page.processed_checksum = metadata["processed_checksum"]
                        page.processing_status = "completed"
                        page.error_message = ""
                        verify_original(resolve(page.source.path), page.source.checksum)
                    db.commit()
                    if job.kind != "detect":
                        remove_file(old_processed)
                        remove_file(old_thumb)
                        remove_file(old_ocr)
                except Exception as exc:
                    db.rollback()
                    page = db.get(Page, page.id)
                    page.processing_status = "failed"
                    page.error_message = "Processing could not complete safely. The original is intact; retry or adjust the boundary."
                    failed += 1
                    log.warning("Page job failed: %s", type(exc).__name__)
                    db.commit()
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                job.completed_pages = index + 1
                job.progress = round((index + 1) / max(1, len(pages)) * (90 if not job.page_id else 100))
                job.lease_until = now() + timedelta(minutes=5)
                db.commit()
            if job.kind == "process" and not job.page_id:
                prefs = get_settings(db, doc.owner_id)
                texts, available = [], True
                for page in doc.pages:
                    if page.ocr_path:
                        texts.append(resolve(page.ocr_path).read_text(encoding="utf-8"))
                        available = available and page.metadata_json.get("ocr", {}).get("available", False)
                result = classify(texts, doc.created_at.year, prefs["filename_language"], prefs["transliterate"], available)
                doc.suggested_name = result["name"]
                doc.detected_type, doc.organization, doc.subject = result["detected_type"], result["organization"], result["subject"]
                doc.detected_date, doc.date_source, doc.description = result["detected_date"], result["date_source"], result["description"]
                if not doc.name_edited:
                    doc.name = result["name"].removesuffix(".pdf")
                    doc.category = result["category"]
                doc.naming_status = "ready" if available else "unavailable"
                doc.updated_at = now()
            job.status = "failed" if failed else "completed"
            job.progress = 100 if not failed else job.progress
            job.error_message = f"{failed} page(s) need attention. Originals are preserved." if failed else ""
            job.completed_at = now()
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            job.status = "failed"
            job.error_message = "The job could not complete safely. Please retry; original sources are preserved."
            job.completed_at = now()
            db.commit()
            log.warning("Job failed: %s", type(exc).__name__)


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (settings.worker_memory_mb * 1024 * 1024,) * 2)
    except (ImportError, ValueError):
        pass
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    recover_stale()
    log.info("Worker ready; local processing only, concurrency=1")
    last_cleanup = 0.0
    while not stop:
        if time.monotonic() - last_cleanup > 3600:
            try:
                with SessionLocal() as db:
                    for user in db.scalars(select(User)).all():
                        cleanup(db, user.id, include_documents=False)
            except Exception as exc:
                log.warning("Periodic cleanup failed: %s", type(exc).__name__)
            last_cleanup = time.monotonic()
        job_id = claim()
        if job_id:
            run_job(job_id)
        else:
            time.sleep(settings.worker_poll_seconds)
    log.info("Worker stopped safely")


if __name__ == "__main__":
    main()
