from pathlib import Path
import fitz
import pikepdf


def inspect_pdf(path: Path, max_pages: int) -> dict:
    with pikepdf.open(path) as pdf:
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported; remove protection locally first")
        count = len(pdf.pages)
        if count < 1 or count > max_pages:
            raise ValueError(f"PDF must contain between 1 and {max_pages} pages")
        return {"pages": count, "encrypted": False}


def render_pdf(path: Path, directory: Path, dpi: int, max_pages: int, max_pixels: int) -> list[dict]:
    inspect_pdf(path, max_pages)
    directory.mkdir(parents=True, exist_ok=True)
    pages = []
    with fitz.open(path) as doc:
        if doc.needs_pass or doc.page_count > max_pages:
            raise ValueError("Invalid or oversized PDF")
        for index, page in enumerate(doc):
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError("Invalid PDF page dimensions")
            pixels = rect.width * rect.height * (dpi / 72) ** 2
            if pixels > max_pixels:
                raise ValueError(f"PDF page {index + 1} exceeds the pixel limit at {dpi} DPI; lower PDF_DPI or split the page")
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csRGB, alpha=False)
            target = directory / f"{index + 1:04d}.png"
            pix.save(target)
            pages.append({"path": target, "width": pix.width, "height": pix.height, "ordinal": index})
            pix = None
    return pages
