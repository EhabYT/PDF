import cv2
import numpy as np
from .detector import order_points


def valid_corners(corners) -> bool:
    try:
        p = np.asarray(corners, dtype=np.float32)
        if p.shape != (4, 2) or not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1):
            return False
        area = cv2.contourArea(p)
        if area < 0.05:
            return False
        edges = np.roll(p, -1, axis=0) - p
        following = np.roll(edges, -1, axis=0)
        crosses = edges[:, 0] * following[:, 1] - edges[:, 1] * following[:, 0]
        return bool(np.all(crosses > 1e-6) or np.all(crosses < -1e-6))
    except (ValueError, TypeError):
        return False


def rotate_corners(corners, degrees):
    p = np.asarray(corners, dtype=np.float32)
    for _ in range((degrees % 360) // 90):
        p = np.column_stack((1 - p[:, 1], p[:, 0]))
    return order_points(p).tolist()


def correct_perspective(rgb: np.ndarray, corners, manual: bool, enabled: bool, max_pixels: int, confidence: float = 0):
    h, w = rgb.shape[:2]
    if not manual and (not enabled or confidence < 0.62):
        return rgb, False
    p = order_points(np.asarray(corners, dtype=np.float32) * [w, h])
    if not manual and np.max(np.abs(p / [w, h] - [[0, 0], [1, 0], [1, 1], [0, 1]])) < 0.025:
        return rgb, False
    # Expand only a very small safe margin; clipping never invents outside pixels.
    center = p.mean(axis=0)
    p = center + (p - center) * 1.006
    p[:, 0] = np.clip(p[:, 0], 0, w - 1)
    p[:, 1] = np.clip(p[:, 1], 0, h - 1)
    tl, tr, br, bl = p
    tw = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    th = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    out_w, out_h = max(2, int(round(tw))), max(2, int(round(th)))
    if out_w * out_h > max_pixels:
        factor = (max_pixels / (out_w * out_h)) ** 0.5
        out_w, out_h = max(2, int(out_w * factor)), max(2, int(out_h * factor))
    dest = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(p.astype(np.float32), dest)
    warped = cv2.warpPerspective(rgb, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return warped, True
