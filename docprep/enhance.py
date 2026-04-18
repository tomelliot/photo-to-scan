"""Post-crop enhancement: shadow removal, white balance, contrast.

Fast CPU-only pipeline (OpenCV + NumPy) applied after geometric correction:
illumination flattening -> paper-anchored white balance -> percentile stretch
on L -> CLAHE on L -> mild unsharp on L. Order matters: flattening first so
every downstream statistic operates on an unbiased field; unsharp last so it
doesn't amplify CLAHE-boosted noise.
"""

import cv2
import numpy as np

from docprep.debug import DebugWriter


def flatten_illumination(bgr: np.ndarray, se_size: int = 51) -> np.ndarray:
    """Remove low-frequency shadows via multiplicative correction on LAB's L."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]

    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (se_size, se_size))
    bg = cv2.morphologyEx(L, cv2.MORPH_CLOSE, se)
    bg = cv2.GaussianBlur(bg, (0, 0), sigmaX=se_size / 3.0).astype(np.float32)

    L_flat = np.clip(L.astype(np.float32) / np.maximum(bg, 1.0) * bg.mean(), 0, 255)
    lab[..., 0] = L_flat.astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def balance_white(
    bgr: np.ndarray, paper_target: tuple[int, int, int] = (245, 245, 245)
) -> np.ndarray:
    """Neutralize paper color cast by matching the largest bright region to target.

    paper_target is given in RGB order (human-intuitive); converted to BGR internally.
    Returns the input unchanged if no paper region can be isolated.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return bgr

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    paper_pixels = bgr[labels == largest].reshape(-1, 3).astype(np.float32)
    if paper_pixels.size == 0:
        return bgr

    paper_bgr = np.percentile(paper_pixels, 75, axis=0)
    target_bgr = np.array(paper_target, dtype=np.float32)[::-1]
    gains = target_bgr / np.maximum(paper_bgr, 1e-6)
    return np.clip(bgr.astype(np.float32) * gains, 0, 255).astype(np.uint8)


def stretch_contrast_L(
    bgr: np.ndarray, low_pct: float = 1.0, high_pct: float = 99.0
) -> np.ndarray:
    """Linear percentile stretch on LAB's L channel (hue preserved)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]
    lo, hi = np.percentile(L, (low_pct, high_pct))
    scale = 255.0 / max(hi - lo, 1.0)
    lab[..., 0] = np.clip((L.astype(np.float32) - lo) * scale, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def apply_clahe_L(
    bgr: np.ndarray, clip: float = 2.0, tile: tuple[int, int] = (8, 8)
) -> np.ndarray:
    """Local micro-contrast via CLAHE on L. Clip kept low to avoid noise boost."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile)
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def unsharp_L(bgr: np.ndarray, sigma: float = 1.2, amount: float = 0.7) -> np.ndarray:
    """Mild unsharp mask on L. Applied last so CLAHE noise isn't amplified."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]
    blur = cv2.GaussianBlur(L, (0, 0), sigmaX=sigma)
    lab[..., 0] = cv2.addWeighted(L, 1.0 + amount, blur, -amount, 0)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def enhance_document(
    bgr: np.ndarray, debug: DebugWriter | None = None
) -> np.ndarray:
    """Run the full enhancement chain and optionally emit per-stage debug images."""
    flat = flatten_illumination(bgr)
    if debug is not None:
        debug.write("03_flattened", flat)

    balanced = balance_white(flat)
    if debug is not None:
        debug.write("04_balanced", balanced)

    stretched = stretch_contrast_L(balanced)
    if debug is not None:
        debug.write("05_stretched", stretched)

    clahe = apply_clahe_L(stretched)
    if debug is not None:
        debug.write("06_clahe", clahe)

    sharp = unsharp_L(clahe)
    if debug is not None:
        debug.write("07_unsharp", sharp)

    return sharp
