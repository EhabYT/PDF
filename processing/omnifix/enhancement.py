import cv2
import numpy as np


def enhance(rgb: np.ndarray, intensity: float = 0.65) -> np.ndarray:
    """One adaptive OmniFix-inspired mode. All operations retain color and marks."""
    intensity = float(np.clip(intensity, 0, 1))
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    luma = lab[:, :, 0]
    clahe = cv2.createCLAHE(clipLimit=1.0 + intensity * 0.65, tileGridSize=(8, 8))
    local = clahe.apply(luma).astype(np.float32)
    mixed = luma.astype(np.float32) * (1 - 0.22 * intensity) + local * 0.22 * intensity
    mixed = (mixed - 128) * (1 + 0.10 * intensity) + 128 + 3 * intensity
    # Gentle highlight roll-off instead of clipping paper to pure white.
    mixed = np.where(mixed > 242, 242 + (mixed - 242) * 0.65, mixed)
    lab[:, :, 0] = np.clip(mixed, 0, 255).astype(np.uint8)
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    # Neutral-paper white balance only, tightly bounded to protect stamps/ink.
    gray = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)
    sat = cv2.cvtColor(result, cv2.COLOR_RGB2HSV)[:, :, 1]
    paper = (gray > np.percentile(gray, 80)) & (sat < 35)
    if paper.mean() > 0.08:
        means = result[paper].mean(axis=0)
        gains = np.clip(means.mean() / np.maximum(means, 1), 0.97, 1.03)
        balanced = result.astype(np.float32) * (1 + (gains - 1) * 0.30 * intensity)
        result = np.clip(balanced, 0, 255).astype(np.uint8)
    small = cv2.resize(cv2.cvtColor(result, cv2.COLOR_RGB2GRAY), (256, 256))
    noise = float(np.median(np.abs(cv2.Laplacian(small, cv2.CV_32F))))
    if noise > 4 and intensity > 0.15:
        smooth = cv2.bilateralFilter(result, 5, 10, 5)
        blend = min(0.18, intensity * 0.20)
        result = cv2.addWeighted(result, 1 - blend, smooth, blend, 0)
    blur = cv2.GaussianBlur(result, (0, 0), 0.8)
    amount = 0.18 + 0.24 * intensity
    return np.clip(cv2.addWeighted(result, 1 + amount, blur, -amount, 0), 0, 255).astype(np.uint8)
