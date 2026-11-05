from pathlib import Path
import img2pdf

SIZES = {"a4": (210, 297), "letter": (215.9, 279.4), "legal": (215.9, 355.6)}


def make_pdf(images: list[Path], output: Path, page_size: str = "a4", orientation: str = "auto", fit: str = "contain"):
    if not images:
        raise ValueError("No selected pages to export")
    if page_size == "original":
        layout = img2pdf.get_layout_fun(None, border=(0, 0), auto_orient=False)
    else:
        w, h = SIZES[page_size]
        if orientation == "landscape":
            w, h = h, w
        layout = img2pdf.get_layout_fun((img2pdf.mm_to_pt(w), img2pdf.mm_to_pt(h)), border=(0, 0), fit=img2pdf.FitMode.into, auto_orient=(orientation == "auto"))
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    with temp.open("wb") as stream:
        img2pdf.convert([str(p) for p in images], outputstream=stream, layout_fun=layout, title="OmniFix processed document", producer="OmniFix Private Scanner", rotation=img2pdf.Rotation.ifvalid)
    temp.replace(output)
