"""Generate synthetic, non-private visual test documents and regression baselines."""
from pathlib import Path
import sys
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import img2pdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from processing.tests.test_engine import synthetic_document
from processing.omnifix.pipeline import process_array
from processing.omnifix.preservation import checksum

OUT = ROOT / "processing/tests/dataset"
OUT.mkdir(parents=True, exist_ok=True)
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font = ImageFont.truetype(font_path, 24)
small = ImageFont.truetype(font_path, 11)

def save(name, rgb):
    Image.fromarray(rgb).save(OUT / f"{name}.png")

save("normal_document", synthetic_document())
save("tilted_document", synthetic_document(tilted=True))
save("shadow_heavy", synthetic_document(shadow=True))
base = synthetic_document().astype(np.float32)
y, x = np.mgrid[0:base.shape[0], 0:base.shape[1]]
gradient = 0.72 + 0.28 * (x / base.shape[1]) + 0.08 * np.sin(y / 90)
save("uneven_illumination", np.clip(base * gradient[:, :, None], 0, 255).astype(np.uint8))
img = Image.new("RGB", (700, 900), (247, 246, 240)); d = ImageDraw.Draw(img)
d.text((60, 60), "Faint handwriting sample", fill=(205, 200, 194), font=small)
d.line((60, 120, 200, 150, 340, 110, 480, 145), fill=(195, 190, 185), width=2)
d.text((60, 220), "Official signature", fill=(70, 80, 140), font=small)
d.line((60, 260, 140, 230, 220, 270, 320, 235), fill=(70, 80, 140), width=2)
save("faint_handwriting", np.asarray(img).copy())
img = Image.new("RGB", (700, 900), (247, 246, 240)); d = ImageDraw.Draw(img)
d.text((60, 60), "Colored stamps and signatures", fill=(30, 30, 30), font=font)
d.ellipse((420, 560, 620, 760), outline=(180, 40, 55), width=5)
d.text((465, 650), "APPROVED", fill=(180, 40, 55), font=small)
d.rectangle((70, 600, 260, 700), outline=(40, 90, 170), width=4)
save("colored_stamps", np.asarray(img).copy())
img = Image.new("RGB", (700, 900), (247, 246, 240)); d = ImageDraw.Draw(img)
d.text((50, 40), "Small text and complex table", fill=(20, 20, 20), font=small)
for row in range(24):
    y0 = 90 + row * 28
    d.line((50, y0, 650, y0), fill=(80, 80, 80), width=1)
    for col in range(6):
        x0 = 50 + col * 100
        d.line((x0, 90, x0, 762), fill=(80, 80, 80), width=1)
        d.text((x0 + 5, y0 + 6), f"R{row}C{col} 12.34", fill=(40, 40, 40), font=small)
save("small_text_table", np.asarray(img).copy())
save("signature_document", synthetic_document())
pages = [OUT / "normal_document.png", OUT / "tilted_document.png", OUT / "small_text_table.png"]
(OUT / "multipage_document.pdf").write_bytes(img2pdf.convert([str(p) for p in pages]))
baseline = {}
for path in sorted(OUT.glob("*.png")):
    rgb = np.asarray(Image.open(path).convert("RGB"))
    output, meta = process_array(rgb)
    import hashlib
    from io import BytesIO
    buffer = BytesIO(); Image.fromarray(output).save(buffer, format="JPEG", quality=95, subsampling=0, dpi=(300, 300), optimize=True)
    baseline[path.name] = {"sha256": hashlib.sha256(buffer.getvalue()).hexdigest(), "shape": list(output.shape), "mean": round(float(output.mean()), 3), "std": round(float(output.std()), 3)}
(OUT / "baseline.json").write_text(json.dumps(baseline, indent=2))
print(f"Generated {len(list(OUT.glob('*.png')))} images, one multi-page PDF and regression baselines in {OUT}")
