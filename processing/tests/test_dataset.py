from pathlib import Path
import json
import numpy as np
from PIL import Image
import pytest
from processing.omnifix.pipeline import process_file
from processing.omnifix.preservation import checksum

DATASET = Path(__file__).parent / "dataset"
CASES = ["normal_document", "tilted_document", "shadow_heavy", "uneven_illumination", "faint_handwriting", "colored_stamps", "small_text_table", "signature_document"]


@pytest.mark.parametrize("name", CASES)
def test_dataset_preservation_determinism_and_dimensions(tmp_path, name):
    source = DATASET / f"{name}.png"
    if not source.exists():
        pytest.skip("Run scripts/generate_test_dataset.py to create the synthetic dataset")
    before = source.read_bytes()
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    m1 = process_file(source, a, checksum(source))
    m2 = process_file(source, b, checksum(source))
    assert source.read_bytes() == before
    assert m1["processed_checksum"] == m2["processed_checksum"]
    assert a.read_bytes() == b.read_bytes()
    with Image.open(a) as image:
        assert image.width >= 2 and image.height >= 2
        assert image.width * image.height <= 24_000_000
    baseline = json.loads((DATASET / "baseline.json").read_text()).get(name + ".png")
    if baseline:
        with Image.open(a) as image:
            arr = np.asarray(image.convert("RGB"))
        assert list(arr.shape) == baseline["shape"]
        assert abs(float(arr.mean()) - baseline["mean"]) < 0.5
        assert abs(float(arr.std()) - baseline["std"]) < 0.5


def test_faint_marks_and_colored_stamp_not_erased():
    source = DATASET / "faint_handwriting.png"
    if not source.exists():
        pytest.skip("dataset not generated")
    original = np.asarray(Image.open(source).convert("RGB"))
    from processing.omnifix.pipeline import process_array
    output, _ = process_array(original, {"auto_detect": False})
    faint_before = original[100:170, 50:500].astype(float).std()
    faint_after = output[100:170, 50:500].astype(float).std()
    assert faint_after >= faint_before * 0.8
    stamp = np.asarray(Image.open(DATASET / "colored_stamps.png").convert("RGB"))
    out_stamp, _ = process_array(stamp, {"auto_detect": False})
    region = out_stamp[560:760, 420:620]
    assert float(region[:, :, 0].mean()) > float(region[:, :, 1].mean()) + 3
