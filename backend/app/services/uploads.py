from pathlib import Path
from uuid import uuid4
import io
import re
import unicodedata
import magic
from PIL import Image
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.errors import AppError
from app.models import Document, SourceFile, Page, User
from app.services.storage import new_path, resolve, immutable, remove_file
from app.services.jobs import enqueue
from app.services.settings import get_settings
from processing.omnifix.preservation import checksum
from processing.pdf.importer import inspect_pdf, render_pdf

EXTENSIONS = {".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".tif": "image", ".tiff": "image", ".pdf": "pdf"}
MIMES = {"image": {"image/jpeg", "image/png", "image/webp", "image/tiff"}, "pdf": {"application/pdf"}}


def clean_filename(filename: str) -> str:
    name = unicodedata.normalize("NFC", filename.replace("\\", "/").split("/")[-1])
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(". ")
    return name[:180] or "upload"


def signature_kind(first: bytes) -> str | None:
    if first.startswith(b"\xff\xd8\xff"):
        return "image"
    if first.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if first[:4] == b"RIFF" and first[8:12] == b"WEBP":
        return "image"
    if first.startswith((b"II*\x00", b"MM\x00*")):
        return "image"
    if first.startswith(b"%PDF-"):
        return "pdf"
    return None


async def receive_uploads(files: list[UploadFile], combine: bool, owner: User, db: Session, target: Document | None = None) -> list[Document]:
    if not files or len(files) > settings.max_pages:
        raise AppError("invalid_upload", f"Upload between 1 and {settings.max_pages} files at once.")
    prefs = get_settings(db, owner.id)
    batch = settings.storage / "temporary" / str(uuid4())
    batch.mkdir(parents=True, exist_ok=True)
    staged, created_paths, documents = [], [], []
    total = 0
    try:
        for upload in files:
            filename = clean_filename(upload.filename or "upload")
            ext = Path(filename).suffix.lower()
            if ext not in EXTENSIONS:
                raise AppError("unsupported_format", "Supported formats: JPG, PNG, WebP, TIFF and PDF.")
            first = await upload.read(64)
            kind = signature_kind(first)
            expected = EXTENSIONS[ext]
            if kind is None or kind != expected:
                raise AppError("invalid_signature", "The file extension does not match its actual content.")
            detected_mime = magic.from_buffer(first, mime=True)
            if detected_mime not in MIMES[kind] and not (kind == "image" and detected_mime == "application/octet-stream" and ext in {".tif", ".tiff"}):
                raise AppError("invalid_mime", "The detected file type is not permitted.")
            limit = (settings.max_pdf_mb if kind == "pdf" else settings.max_file_mb) * 1024 * 1024
            temp_target = batch / f"{uuid4()}{ext}"
            size = 0
            with temp_target.open("xb") as stream:
                chunk = first
                while chunk:
                    size += len(chunk)
                    total += len(chunk)
                    if size > limit or total > settings.max_upload_mb * 1024 * 1024:
                        raise AppError("file_too_large", f"Upload limits: {settings.max_file_mb} MB per image, {settings.max_pdf_mb} MB per PDF, {settings.max_upload_mb} MB per request.")
                    stream.write(chunk)
                    chunk = await upload.read(1024 * 1024)
            if kind == "pdf":
                try:
                    info = inspect_pdf(temp_target, settings.max_pages)
                except Exception:
                    raise AppError("invalid_pdf", "This PDF is invalid, encrypted or exceeds the page limit.")
                staged.append({"temp": temp_target, "filename": filename, "kind": kind, "size": size, "mime": "application/pdf", "pages": info["pages"], "width": 0, "height": 0})
            else:
                try:
                    with Image.open(temp_target) as image:
                        image.verify()
                    with Image.open(temp_target) as image:
                        w, h = image.size
                        if w < 2 or h < 2 or w * h > settings.max_pixels:
                            raise ValueError("dimensions")
                        if getattr(image, "n_frames", 1) > 1:
                            raise ValueError("multiframe")
                        mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "TIFF": "image/tiff"}[image.format]
                    staged.append({"temp": temp_target, "filename": filename, "kind": kind, "size": size, "mime": mime, "pages": 1, "width": w, "height": h})
                except ValueError as exc:
                    if str(exc) == "multiframe":
                        raise AppError("multiframe", "Multi-frame images must be uploaded as separate pages or a PDF.")
                    raise AppError("invalid_image", "The image is corrupt or exceeds the configured resolution.")
                except Exception:
                    raise AppError("invalid_image", "The image could not be safely decoded.")
            if sum(x["pages"] for x in staged) > settings.max_pages:
                raise AppError("too_many_pages", f"A document may contain at most {settings.max_pages} pages.")
        if target and sum(x["pages"] for x in staged) + len(target.pages) > settings.max_pages:
            raise AppError("too_many_pages", f"A document may contain at most {settings.max_pages} pages.")
        groups = [staged] if combine or target else [[item] for item in staged]
        for group in groups:
            first = group[0]
            doc = target or Document(owner_id=owner.id, name=Path(first["filename"]).stem[:120], original_filename=first["filename"], document_type="mixed" if len({x["kind"] for x in group}) > 1 else first["kind"])
            if target:
                doc.document_type = "mixed" if doc.document_type != first["kind"] else doc.document_type
                doc.name_edited = True  # adding pages must not silently replace an approved name
            if not target:
                db.add(doc)
            db.flush()
            ordinal = len(doc.pages)
            for item in group:
                rel, path = new_path(f"originals/{'pdfs' if item['kind'] == 'pdf' else 'images'}", item["temp"].suffix)
                item["temp"].replace(path)
                immutable(path)
                created_paths.append(rel)
                digest = checksum(path)
                source = SourceFile(document_id=doc.id, filename=item["filename"], path=rel, checksum=digest, size=item["size"], mime=item["mime"], kind=item["kind"], width=item["width"], height=item["height"])
                db.add(source)
                db.flush()
                if item["kind"] == "pdf":
                    render_rel = f"originals/renders/{uuid4()}"
                    try:
                        rendered = render_pdf(path, resolve(render_rel), prefs["pdf_dpi"], settings.max_pages, settings.max_pixels)
                    except Exception:
                        raise AppError("pdf_render_failed", "A PDF page could not be rendered within the configured safety limits.")
                    for render in rendered:
                        rp = str(render["path"].relative_to(settings.storage))
                        created_paths.append(rp)
                        immutable(render["path"])
                        db.add(Page(document_id=doc.id, source_id=source.id, ordinal=ordinal, original_path=rp, checksum=checksum(render["path"]), width=render["width"], height=render["height"]))
                        ordinal += 1
                else:
                    db.add(Page(document_id=doc.id, source_id=source.id, ordinal=ordinal, original_path=rel, checksum=digest, width=item["width"], height=item["height"]))
                    ordinal += 1
            documents.append(doc)
        db.commit()
        for doc in documents:
            db.refresh(doc)
            if prefs["auto_process"] and prefs["processing_enabled"]:
                enqueue(db, doc)
        return documents
    except Exception:
        db.rollback()
        for rel in created_paths:
            remove_file(rel)
        raise
    finally:
        for upload in files:
            await upload.close()
        for p in batch.glob("*"):
            p.unlink(missing_ok=True)
        batch.rmdir()
