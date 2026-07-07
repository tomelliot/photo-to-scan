"""Post-crop enhancement: shadow removal, white balance, contrast.

Fast CPU-only pipeline (OpenCV + NumPy) applied after geometric correction:
illumination flattening -> paper-anchored white balance -> white-point scale
on L -> global S-curve on L -> mild unsharp on L. Order matters: flattening
first so every downstream statistic operates on an unbiased field; unsharp
last so it doesn't amplify contrast-boosted noise.

The flatten background estimate and the contrast stages are deliberately
non-spatial or ink-masked: morphological envelopes (close/dilate) and CLAHE
both darkened the paper immediately around text (ablation suite, 2026-07-07),
because their estimates are biased exactly where paper meets ink.
"""

import cv2
import numpy as np

from docprep.debug import DebugWriter


def flatten_illumination(bgr: np.ndarray, window: int | None = None) -> np.ndarray:
    """Remove low-frequency shadows via multiplicative correction on LAB's L.

    The background is estimated as the mean of *paper pixels only* in each
    neighborhood (normalized convolution over an ink mask). Ink never enters
    the estimate, so the paper right next to a glyph is corrected exactly like
    open paper — a morphological close here left a dark ring around text.

    window defaults to ~1/8 of the short image side so behaviour is stable
    across input resolutions.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]
    if window is None:
        window = max(31, (min(L.shape) // 8) | 1)

    _, ink = cv2.threshold(L, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    paper = (ink == 0).astype(np.float32)
    Lf = L.astype(np.float32)

    num = cv2.boxFilter(Lf * paper, -1, (window, window), normalize=False)
    den = cv2.boxFilter(paper, -1, (window, window), normalize=False)
    bg = num / np.maximum(den, 1.0)
    fallback = float(np.median(Lf[paper > 0])) if paper.any() else 255.0
    bg[den < 1.0] = fallback  # windows with no paper at all (e.g. bold headings)
    bg = np.maximum(cv2.GaussianBlur(bg, (0, 0), sigmaX=window / 6.0), 1.0)

    lab[..., 0] = np.clip(Lf / bg * bg.mean(), 0, 255).astype(np.uint8)
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


def whitepoint_L(bgr: np.ndarray, pct: float = 90.0) -> np.ndarray:
    """Scale L so the paper level (bright percentile) maps to white.

    Unlike a two-sided percentile stretch there is no black-point anchor, so
    small local residues from flattening are not amplified into visible rings.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0].astype(np.float32)
    p = max(float(np.percentile(L, pct)), 1.0)
    lab[..., 0] = np.clip(L * (255.0 / p), 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def scurve_L(bgr: np.ndarray, strength: float = 6.0, mid: float = 0.55) -> np.ndarray:
    """Global sigmoid contrast on L: darkens ink, pushes paper toward white.

    Purely tonal (no spatial component), so unlike CLAHE it cannot darken one
    neighborhood relative to another.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    x = lab[..., 0].astype(np.float32) / 255.0
    s = 1.0 / (1.0 + np.exp(-strength * (x - mid)))
    lo = 1.0 / (1.0 + np.exp(strength * mid))
    hi = 1.0 / (1.0 + np.exp(-strength * (1.0 - mid)))
    lab[..., 0] = np.clip((s - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def unsharp_L(bgr: np.ndarray, sigma: float = 1.0, amount: float = 0.35) -> np.ndarray:
    """Mild unsharp mask on L. Applied last, and kept gentle: stronger amounts
    put a visible dark rim around glyph edges."""
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

    white = whitepoint_L(balanced)
    if debug is not None:
        debug.write("05_whitepoint", white)

    curved = scurve_L(white)
    if debug is not None:
        debug.write("06_scurve", curved)

    sharp = unsharp_L(curved)
    if debug is not None:
        debug.write("07_unsharp", sharp)

    return sharp
