from pathlib import Path
from uuid import uuid4
from datetime import timedelta
import json
import zipfile
from PIL import Image
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Document, ProcessingJob, Export, Page, now
from app.services.storage import new_path, resolve
from processing.omnifix.preservation import checksum, verify_original
from processing.omnifix.naming import safe_filename
from processing.pdf.exporter import make_pdf


def run_export(db: Session, job: ProcessingJob):
    doc = db.get(Document, job.document_id)
    if not doc:
        raise ValueError("Document no longer exists")
    opts = job.settings_snapshot
    fmt = job.kind.removeprefix("export_")
    selected_ids = opts.get("page_ids")
    pages = [p for p in doc.pages if p.included and (not selected_ids or p.id in selected_ids)]
    if not pages:
        raise ValueError("No selected pages")
    filename = safe_filename(opts.get("filename") or doc.approved_name or doc.suggested_name or doc.name, "")
    job.total_pages = len(pages)
    if fmt != "originals" and any(p.processing_status != "completed" or not p.processed_path for p in pages):
        raise ValueError("Process all selected pages before exporting")
    for page in pages:
        verify_original(resolve(page.original_path), page.checksum)
        verify_original(resolve(page.source.path), page.source.checksum)
    rel, output = new_path("exports", ".pdf" if fmt == "pdf" else ".zip")
    work = settings.storage / "temporary" / f"export-{uuid4()}"
    work.mkdir(parents=True)
    try:
        image_paths = []
        if fmt in {"pdf", "images", "zip"}:
            for index, page in enumerate(pages):
                source = resolve(page.processed_path)
                if opts.get("quality", 95) != 95:
                    target = work / f"page_{index + 1:04d}.jpg"
                    with Image.open(source) as image:
                        image.save(target, "JPEG", quality=opts["quality"], subsampling=0, dpi=(300, 300))
                    source = target
                image_paths.append(source)
                job.completed_pages = index + 1
                job.progress = round((index + 1) / len(pages) * 85)
                db.commit()
        if fmt == "pdf":
            make_pdf(image_paths, output, opts.get("page_size", "a4"), opts.get("orientation", "auto"))
        elif fmt == "originals":
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for index, source in enumerate(doc.sources):
                    verify_original(resolve(source.path), source.checksum)
                    archive.write(resolve(source.path), f"{index + 1:03d}_{source.filename}")
        else:
            pdf_path = work / "document.pdf"
            make_pdf(image_paths, pdf_path, opts.get("page_size", "a4"), opts.get("orientation", "auto"))
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                if fmt == "zip":
                    archive.write(pdf_path, f"{filename}.pdf")
                    archive.writestr("document.json", json.dumps({"name": doc.name, "category": doc.category, "pages": len(pages), "engine": "OmniFix", "generative_ai": False}, ensure_ascii=False, indent=2))
                for index, path in enumerate(image_paths):
                    archive.write(path, f"{filename}_page_{index + 1:03d}.jpg")
        digest = checksum(output)
        item = Export(document_id=doc.id, filename=filename + (".pdf" if fmt == "pdf" else ".zip"), path=rel, format=fmt, size=output.stat().st_size, checksum=digest, page_ids=[p.id for p in pages], expires_at=now() + timedelta(days=opts.get("export_retention_days", 30)))
        db.add(item)
        doc.updated_at = now()
        job.progress = 100
        job.status = "completed"
        job.completed_at = now()
        db.commit()
    except Exception:
        output.unlink(missing_ok=True)
        raise
    finally:
        for path in work.glob("*"):
            path.unlink(missing_ok=True)
        work.rmdir()
