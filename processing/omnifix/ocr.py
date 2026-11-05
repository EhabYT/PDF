from pathlib import Path
import shutil
import pytesseract
from PIL import Image, ImageOps


def available_languages(command: str = "tesseract") -> list[str]:
    if not shutil.which(command):
        return []
    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


def recognize(path: Path, command: str, languages: str, timeout: int) -> tuple[str, dict]:
    installed = available_languages(command)
    requested = [x for x in languages.split("+") if x in installed]
    if not requested:
        return "", {"available": False, "reason": "Local OCR language models are not installed", "languages": []}
    pytesseract.pytesseract.tesseract_cmd = command
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
        text = pytesseract.image_to_string(image, lang="+".join(requested), config="--psm 3", timeout=timeout)
    text = text[:200_000]
    return text, {"available": True, "languages": requested, "characters": len(text), "engine": "Tesseract local", "external_upload": False}
