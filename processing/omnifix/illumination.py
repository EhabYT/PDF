import cv2
import numpy as np


def normalize_illumination(rgb: np.ndarray, intensity: float, shadow_correction: bool, analysis: dict) -> np.ndarray:
    """Color-preserving LAB illumination normalization; no white threshold."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    luma = lab[:, :, 0]
    h, w = luma.shape
    scale = min(1.0, 384 / max(h, w))
    small = cv2.resize(luma, (max(8, round(w * scale)), max(8, round(h * scale))), interpolation=cv2.INTER_AREA)
    sigma = max(3.0, min(small.shape[:2]) / 10)
    background = cv2.GaussianBlur(small, (0, 0), sigma)
    background = cv2.resize(background, (w, h), interpolation=cv2.INTER_CUBIC)
    target = float(np.percentile(background, 85))
    target = min(242.0, max(185.0, target))
    gain = np.clip(target / np.maximum(background, 65), 0.85, 1.65)
    shadow = min(1.0, analysis.get("shadow_fraction", 0) * 4)
    strength = intensity * (0.62 + 0.25 * shadow) if shadow_correction else intensity * 0.20
    lab[:, :, 0] = np.clip(luma * (1 + (gain - 1) * strength), 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
