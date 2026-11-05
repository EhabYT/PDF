import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import pytest
from processing.omnifix.pipeline import process_array, process_file, read_oriented
from processing.omnifix.detector import detect_document
from processing.omnifix.geometry import valid_corners, rotate_corners
from processing.omnifix.naming import classify, safe_filename
from processing.omnifix.preservation import checksum


def synthetic_document(shadow=False, tilted=False):
    rng = np.random.default_rng(42)
    bg = np.full((900, 700, 3), 95, np.uint8)
    paper = np.full((620, 460, 3), 238, np.uint8)
    image = Image.fromarray(paper)
    d = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((30, 30), "Mietvertrag Stadt Essen", fill=(30, 30, 30), font=font)
    d.text((30, 80), "12.03.2026", fill=(60, 60, 60), font=small)
    for y in range(130, 450, 28):
        d.line((30, y, 420, y), fill=(90, 90, 90), width=1)
    d.text((30, 480), "faint signature", fill=(185, 180, 175), font=small)
    d.ellipse((310, 490, 420, 590), outline=(180, 40, 50), width=4)
    paper = np.asarray(image).copy()
    if shadow:
        x = np.linspace(0.55, 1.0, paper.shape[1])[None, :, None]
        paper = np.clip(paper * x, 0, 255).astype(np.uint8)
    if tilted:
        src = np.float32([[0, 0], [459, 0], [459, 619], [0, 619]])
        dst = np.float32([[170, 100], [570, 150], [540, 790], [120, 740]])
        matrix = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(paper, matrix, (700, 900), borderValue=(95, 95, 95))
        mask = cv2.warpPerspective(np.ones((620, 460), np.uint8), matrix, (700, 900))
        bg[mask > 0] = warped[mask > 0]
        return bg
    bg[130:750, 120:580] = paper
    return bg


def test_detection_confident_on_synthetic_page():
    rgb = synthetic_document()
    result = detect_document(rgb)
    assert result["confidence"] >= .62
    assert result["method"] == "quadrilateral"
    assert valid_corners(result["corners"])


def test_low_confidence_preserves_full_frame():
    rgb = np.full((400, 400, 3), 220, np.uint8)
    result = detect_document(rgb)
    assert result["corners"] == [[0, 0], [1, 0], [1, 1], [0, 1]]
    output, meta = process_array(rgb)
    assert meta["perspective_applied"] is False
    assert output.shape[:2] == rgb.shape[:2]


def test_perspective_correction_valid_output():
    rgb = synthetic_document(tilted=True)
    output, meta = process_array(rgb)
    assert meta["perspective_applied"] is True
    assert output.shape[0] > 400 and output.shape[1] > 300
    assert output.shape[0] * output.shape[1] <= 24_000_000


def test_shadow_correction_and_color_preservation():
    rgb = synthetic_document(shadow=True)
    output, meta = process_array(rgb, {"intensity": .65, "auto_detect": False})
    assert output.shape == rgb.shape
    stamp = output[620:720, 430:540]
    assert float(stamp[:, :, 0].mean()) > float(stamp[:, :, 1].mean()) + 5
    faint = output[600:625, 150:300]
    assert float(faint.std()) > 1


def test_deterministic_and_original_integrity(tmp_path):
    source = tmp_path / "original.png"
    Image.fromarray(synthetic_document()).save(source)
    before = source.read_bytes()
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    meta1 = process_file(source, a, checksum(source))
    meta2 = process_file(source, b, checksum(source))
    assert source.read_bytes() == before
    assert meta1["processed_checksum"] == meta2["processed_checksum"]
    assert a.read_bytes() == b.read_bytes()


def test_rotation_corners_and_validation():
    corners = [[.1, .2], [.8, .2], [.8, .9], [.1, .9]]
    rotated = rotate_corners(corners, 90)
    assert valid_corners(rotated)
    assert not valid_corners([[0, 0], [1, 1], [0, 1], [1, 0]])
    assert not valid_corners([[0, 0], [1, 0], [1, 1], [2, 1]])


def test_multilingual_naming_rules():
    rental = classify(["Mietvertrag\nStadt Essen\n12.03.2026"], 2026)
    assert rental["category"] == "Rental Agreements"
    assert rental["name"] == "Mietvertrag_Essen_03-2026.pdf"
    bank = classify(["Sparkasse Düsseldorf\nKontoauszug\nNovember 2026"], 2026, "en")
    assert bank["category"] == "Bank Statements"
    arabic = classify(["عقد إيجار\n٢٠٢٦"], 2026, "ar")
    assert arabic["category"] == "Rental Agreements"
    assert arabic["name"].endswith(".pdf")


def test_unknown_is_conservative_and_filename_safe():
    result = classify(["random unclear marks"], 2026)
    assert result["name"] == "Unbekanntes_Dokument_2026.pdf"
    assert result["date_source"] == "upload"
    assert safe_filename("../../etc/passwd.pdf") == "etc_passwd.pdf"
    assert safe_filename("name.pdf.pdf").endswith(".pdf")
    assert not safe_filename("a" * 300).count("/")
