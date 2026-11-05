"""Conservative, deterministic document detection. Never invents a crop."""
import cv2
import numpy as np

cv2.setNumThreads(1)
FULL = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def order_points(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = p.mean(axis=0)
    angles = np.arctan2(p[:, 1] - center[1], p[:, 0] - center[0])
    p = p[np.argsort(angles)]
    start = int(np.argmin(p.sum(axis=1)))
    return np.roll(p, -start, axis=0)


def analyze(rgb: np.ndarray) -> dict:
    h, w = rgb.shape[:2]
    scale = min(1.0, 600 / max(h, w))
    small = cv2.resize(rgb, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    mean, std = float(gray.mean()), float(gray.std())
    return {"mean_brightness": round(mean, 2), "contrast": round(std, 2), "shadow_fraction": round(float((gray < mean * 0.72).mean()), 4), "background_uniformity": round(float(border.std()), 2), "orientation": "upright_reference", "pipeline": "OMNIFIX", "version": "1.0.0"}


def detect_document(rgb: np.ndarray, enabled: bool = True) -> dict:
    analysis = analyze(rgb)
    result = {**analysis, "corners": FULL, "confidence": 0.0, "method": "full_frame", "perspective_applied": False}
    if not enabled:
        result["method"] = "detection_disabled"
        return result
    h, w = rgb.shape[:2]
    scale = min(1.0, 1000 / max(h, w))
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    median = float(np.median(blur))
    edges = cv2.Canny(blur, int(max(20, 0.6 * median)), int(min(220, max(60, 1.3 * median))))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    best, best_score = None, 0.0
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:25]:
        area = cv2.contourArea(contour) / (sw * sh)
        if area < 0.15 or area > 0.985:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * peri, True)
        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        if rw < 10 or rh < 10:
            continue
        rectangularity = min(1.0, area / max(1.0, rw * rh / (sw * sh)))
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype(np.float32)
        elif rectangularity > 0.94:
            quad = cv2.boxPoints(rect)
        else:
            continue
        quad = order_points(quad)
        mask = np.zeros_like(gray)
        for a, b in zip(quad, np.roll(quad, -1, axis=0)):
            cv2.line(mask, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), 255, 3)
        edge_strength = min(1.0, float(gradient[mask > 0].mean()) / 180) if np.any(mask) else 0
        side = np.linalg.norm(quad - np.roll(quad, -1, axis=0), axis=1)
        aspect = max(side) / max(1, min(side))
        if aspect > 8:
            continue
        score = 0.50 * rectangularity + 0.35 * edge_strength + 0.15 * min(1, area / 0.5)
        if score > best_score:
            best_score, best = score, quad
    if best is not None and best_score >= 0.62:
        corners = np.clip(best / [sw, sh], 0, 1)
        deviation = float(np.max(np.abs(corners - np.array(FULL))))
        result.update(corners=np.round(corners, 6).tolist(), confidence=round(best_score, 4), method="quadrilateral", perspective_candidate=deviation > 0.025)
    else:
        result["reason"] = "No sufficiently confident four-sided boundary; full source retained."
    return result
