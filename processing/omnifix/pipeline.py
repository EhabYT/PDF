from pathlib import Path
import io
import numpy as np
from PIL import Image, ImageOps
import cv2
from .detector import detect_document
from .geometry import correct_perspective, valid_corners
from .illumination import normalize_illumination
from .enhancement import enhance
from .preservation import checksum, verify_original

VERSION = "1.0.0"
DEFAULTS = {"intensity": 0.65, "auto_detect": True, "auto_correct": True, "shadow_correction": True, "max_output_pixels": 24_000_000}


def read_oriented(path: Path, max_pixels: int = 40_000_000) -> np.ndarray:
    with Image.open(path) as image:
        image.load()
        if image.width * image.height > max_pixels:
            raise ValueError("Image exceeds the configured pixel limit")
        image = ImageOps.exif_transpose(image).convert("RGB")
        return np.asarray(image).copy()


def rotate(rgb: np.ndarray, degrees: int) -> np.ndarray:
    return np.rot90(rgb, k=-((degrees % 360) // 90)).copy()


def process_array(rgb: np.ndarray, options: dict | None = None, corners=None, manual: bool = False) -> tuple[np.ndarray, dict]:
    opts = {**DEFAULTS, **(options or {})}
    intensity = max(0.0, min(1.0, float(opts["intensity"])))
    detection = detect_document(rgb, opts["auto_detect"])
    selected = corners if corners is not None else detection["corners"]
    if not valid_corners(selected):
        raise ValueError("Invalid document boundary")
    corrected, applied = correct_perspective(rgb, selected, manual, opts["auto_correct"], int(opts["max_output_pixels"]), detection["confidence"])
    normalized = normalize_illumination(corrected, intensity, opts["shadow_correction"], detection)
    output = enhance(normalized, intensity)
    detection.update(perspective_applied=applied, manual_boundary=manual, intensity=intensity, input_shape=list(rgb.shape[:2]), output_shape=list(output.shape[:2]), deterministic=True, generative_ai=False)
    return output, detection


def save_image(rgb: np.ndarray, path: Path, quality: int = 95):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(rgb)
    temp = path.with_suffix(path.suffix + ".tmp")
    image.save(temp, format="JPEG", quality=max(80, min(100, quality)), subsampling=0, dpi=(300, 300), optimize=True)
    temp.replace(path)


def process_file(source: Path, output: Path, expected_checksum: str, options: dict | None = None, corners=None, manual: bool = False, rotation: int = 0, max_pixels: int = 40_000_000) -> dict:
    verify_original(source, expected_checksum)
    rgb = rotate(read_oriented(source, max_pixels), rotation)
    result, metadata = process_array(rgb, options, corners, manual)
    save_image(result, output)
    verify_original(source, expected_checksum)
    metadata.update(original_checksum=expected_checksum, processed_checksum=checksum(output), engine="OmniFix Engine", mode="OMNIFIX", version=VERSION)
    return metadata


def thumbnail(source: Path, output: Path, size: int = 480):
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, "JPEG", quality=86, optimize=True)
