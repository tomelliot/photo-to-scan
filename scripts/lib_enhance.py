"""Prototype: try several off-the-shelf library approaches to document
enhancement and emit outputs for visual comparison.

Inputs: docs/examples/example_NN_processed.jpg (pre-enhance crop+deskew).
Outputs: ablation_out/example_NN_<method>.jpg for each method.

The specific problem we're targeting: the previous pipeline's flatten_illumination
leaves darkness in empty space *between* text. That's a sign the morphological
background estimator (51px SE) has text mass leaking into the local background.
The methods below are all variants of "estimate paper background more cleanly,
then divide".

Methods:
  baseline      - original input, no processing
  raw_flatten   - current repo's flatten_illumination only (for reference)
  sk_rollball   - skimage.restoration.rolling_ball: estimate background as
                  the surface a ball of radius R rolls under. Designed to
                  ignore "bumps" like text. Divide by it.
  sk_sauvola    - skimage.filters.threshold_sauvola gives a per-pixel local
                  mean+std threshold; use its local mean as the paper value
                  and divide.
  sk_adapthist  - skimage.exposure.equalize_adapthist (CLAHE) with a very
                  large kernel relative to text, plus post-anchoring of whites.
  big_blur_div  - pure OpenCV baseline: Gaussian-blur with sigma >> text
                  stroke width, divide by that. Same idea as flatten but with
                  a kernel far bigger than glyphs.
  pil_autocon   - PIL.ImageOps.autocontrast with preserve_tone — bare-minimum
                  baseline, no locality.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from skimage import exposure, img_as_float, img_as_ubyte
from skimage.filters import threshold_sauvola
from skimage.restoration import rolling_ball

EXAMPLES_DIR = Path("docs/examples")
OUT_DIR = Path("ablation_out")


def _to_gray_float(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)


def _apply_L_map(bgr: np.ndarray, L_new: np.ndarray) -> np.ndarray:
    """Replace LAB's L with a new (0-255) array and return BGR."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    lab[..., 0] = np.clip(L_new, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def raw_flatten(bgr: np.ndarray) -> np.ndarray:
    """Repo's flatten_illumination, verbatim, for reference."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]
    se_size = 51
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (se_size, se_size))
    bg = cv2.morphologyEx(L, cv2.MORPH_CLOSE, se)
    bg = cv2.GaussianBlur(bg, (0, 0), sigmaX=se_size / 3.0).astype(np.float32)
    L_flat = np.clip(L.astype(np.float32) / np.maximum(bg, 1.0) * bg.mean(), 0, 255)
    lab[..., 0] = L_flat.astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def sk_rollball(bgr: np.ndarray, radius: int = 60) -> np.ndarray:
    """skimage rolling ball: ball rolls under the surface. radius should
    exceed the thickest text stroke so text doesn't push the ball down."""
    L = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0]
    # rolling_ball estimates a background *darker* than the image by default;
    # for dark-text-on-light-paper we invert, roll, then invert back.
    inverted = 255 - L
    bg = rolling_ball(inverted, radius=radius)
    paper = 255 - bg  # the estimated local paper brightness
    out = L.astype(np.float32) / np.maximum(paper.astype(np.float32), 1.0) * 255.0
    return _apply_L_map(bgr, out)


def sk_sauvola(bgr: np.ndarray, window: int = 75, k: float = 0.2) -> np.ndarray:
    """Use the local mean (what Sauvola uses as a threshold base) as paper
    and divide. Retains grayscale — we only want the locality, not binarization."""
    L = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0]
    L_float = img_as_float(L)
    # threshold_sauvola returns a per-pixel threshold = mean - k*std*(delta)
    # For a paper estimate we want just the local mean; compute via uniform filter.
    # Cheat: sauvola with k=0 gives mean-ish threshold. Use a direct local mean.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (window, window))
    # A morphological dilation approximates "max in window" == paper brightness
    local_paper = cv2.dilate(L, kernel)
    local_paper = cv2.GaussianBlur(local_paper, (0, 0), sigmaX=window / 3.0).astype(
        np.float32
    )
    out = L.astype(np.float32) / np.maximum(local_paper, 1.0) * 255.0
    # Silence unused-import warnings — keep sauvola reference for the docstring.
    _ = threshold_sauvola(L_float, window_size=window, k=k)
    return _apply_L_map(bgr, out)


def sk_adapthist(bgr: np.ndarray, clip_limit: float = 0.01) -> np.ndarray:
    """skimage equalize_adapthist (CLAHE) with kernel_size sized to the image
    (default kernel_size = image/8 which is 8x8 tiles — same issue as OpenCV
    CLAHE). Use a much larger kernel and low clip, then re-anchor whites."""
    L = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0]
    h, w = L.shape
    ksize = (max(h // 3, 1), max(w // 3, 1))  # large tiles: 3x3 across image
    eq = exposure.equalize_adapthist(L, kernel_size=ksize, clip_limit=clip_limit)
    eq_u8 = img_as_ubyte(eq).astype(np.float32)
    # Anchor: push 95th pct toward 252 via gain (never darkens)
    paper = float(np.percentile(eq_u8, 95))
    if paper >= 1:
        gain = max(252.0 / paper, 1.0)
        eq_u8 = np.clip(eq_u8 * gain, 0, 255)
    return _apply_L_map(bgr, eq_u8)


def big_blur_div(bgr: np.ndarray, sigma: int = 60) -> np.ndarray:
    """Baseline: pure OpenCV — Gaussian blur with sigma much bigger than any
    text stroke, then divide. Simple but surprisingly effective when sigma
    is big enough that text is smeared into the background estimate."""
    L = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0]
    bg = cv2.GaussianBlur(L, (0, 0), sigmaX=sigma).astype(np.float32)
    out = L.astype(np.float32) / np.maximum(bg, 1.0) * bg.mean()
    return _apply_L_map(bgr, out)


def pil_autocon(bgr: np.ndarray) -> np.ndarray:
    """PIL ImageOps.autocontrast with small cutoff. Global, no locality.
    Included as the 'if this is enough, don't bother with libraries' baseline."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    out = ImageOps.autocontrast(pil, cutoff=1, preserve_tone=True)
    return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)


def flatten_then_autocon(bgr: np.ndarray) -> np.ndarray:
    """Shadow removal first, then PIL autocontrast. Tests whether the
    autocontrast shadow-crush (p1 -> 0) is caused by the uneven input;
    if flatten first pulls all paper to one tight band near white, the
    autocontrast stretch has no dark non-text pixels to force to 0."""
    return pil_autocon(raw_flatten(bgr))


def flatten_then_lift(
    bgr: np.ndarray, paper_pct: float = 99.0, paper_target: int = 253
) -> np.ndarray:
    """Shadow removal, then a white-point-only lift on L. Unlike autocontrast
    this does NOT touch the black point — darks stay where they are, paper
    is nudged up toward white by a single gain (clamped >= 1 so nothing
    darkens). Uses p99 rather than p95 as the paper anchor because after
    flatten, paper is very uniform and p99 is a better estimate of 'true
    paper' (less chance of text bleeding in)."""
    flat = raw_flatten(bgr)
    lab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB)
    L = lab[..., 0].astype(np.float32)
    paper_L = float(np.percentile(L, paper_pct))
    if paper_L < 1.0:
        return flat
    gain = paper_target / paper_L
    if gain <= 1.0:
        return flat
    lab[..., 0] = np.clip(L * gain, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


METHODS = {
    "baseline": lambda img: img,
    "raw_flatten": raw_flatten,
    "sk_rollball": sk_rollball,
    "sk_sauvola": sk_sauvola,
    "sk_adapthist": sk_adapthist,
    "big_blur_div": big_blur_div,
    "pil_autocon": pil_autocon,
    "flatten_autocon": flatten_then_autocon,
    "flatten_lift": flatten_then_lift,
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    sources = sorted(EXAMPLES_DIR.glob("example_*_processed.jpg"))
    if not sources:
        raise SystemExit(f"No inputs in {EXAMPLES_DIR}")

    for src in sources:
        img = cv2.imread(str(src))
        if img is None:
            print(f"!! could not read {src}")
            continue
        stem = src.stem.removesuffix("_processed")
        for name, fn in METHODS.items():
            print(f"{src.name} [{name}]", flush=True)
            result = fn(img)
            out = OUT_DIR / f"{stem}_{name}.jpg"
            cv2.imwrite(str(out), result)


if __name__ == "__main__":
    main()
