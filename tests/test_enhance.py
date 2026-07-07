"""Tests for docprep.enhance: each stage + end-to-end."""

import cv2
import numpy as np

from docprep.enhance import (
    balance_white,
    enhance_document,
    flatten_illumination,
    scurve_L,
    unsharp_L,
    whitepoint_L,
)


def _paper_with_shadow(h: int = 240, w: int = 240, base: int = 220) -> np.ndarray:
    """Uniform paper (BGR = base) darkened by a left-to-right illumination ramp."""
    ramp = np.linspace(0.5, 1.0, w, dtype=np.float32)[None, :, None]
    img = np.full((h, w, 3), base, dtype=np.float32) * ramp
    return np.clip(img, 0, 255).astype(np.uint8)


def _add_text_lines(img: np.ndarray, value: int = 40) -> np.ndarray:
    """Draw text-like dark strokes in the upper half of the page."""
    out = img.copy()
    h, w = out.shape[:2]
    for y in range(20, h // 2, 16):
        cv2.line(out, (20, y), (w - 40, y), (value, value, value), 3)
    return out


def test_flatten_illumination_removes_gradient():
    img = _add_text_lines(_paper_with_shadow())

    # Judge flatness on an ink-free row near the bottom of the page.
    row = -20
    before = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[row, :, 0]
    after = cv2.cvtColor(flatten_illumination(img), cv2.COLOR_BGR2LAB)[row, :, 0]

    assert after.std() < before.std() * 0.5


def test_flatten_illumination_no_dark_ring_around_text():
    """Regression: the close+blur background estimate darkened paper right
    next to ink relative to open paper (visible halo around text blocks)."""
    img = _add_text_lines(np.full((240, 240, 3), 220, dtype=np.uint8))

    L = cv2.cvtColor(flatten_illumination(img), cv2.COLOR_BGR2LAB)[..., 0]
    ink = (cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0] < 128).astype(np.uint8) * 255
    near = cv2.dilate(ink, np.ones((9, 9), np.uint8)) & ~ink
    far = ~cv2.dilate(ink, np.ones((41, 41), np.uint8))

    halo = float(np.median(L[near > 0])) - float(np.median(L[far > 0]))
    assert abs(halo) <= 3


def test_balance_white_neutralizes_cast():
    # Cool off-white paper: stronger blue/green than red.
    img = np.full((200, 200, 3), (240, 230, 220), dtype=np.uint8)  # BGR

    balanced = balance_white(img, paper_target=(245, 245, 245))
    mean_bgr = balanced.reshape(-1, 3).mean(axis=0)

    # All channels should land near the target (neutral) within a small tolerance.
    assert np.allclose(mean_bgr, (245, 245, 245), atol=5)


def test_balance_white_handles_solid_image():
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    # No paper region can be robustly isolated — must not raise.
    out = balance_white(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_whitepoint_maps_paper_to_white():
    img = _add_text_lines(np.full((240, 240, 3), 200, dtype=np.uint8))

    L = cv2.cvtColor(whitepoint_L(img), cv2.COLOR_BGR2LAB)[..., 0]
    paper = L[-20, :]  # ink-free row

    assert np.median(paper) >= 250


def test_scurve_darkens_ink_and_lightens_paper():
    img = _add_text_lines(np.full((240, 240, 3), 220, dtype=np.uint8), value=80)

    L_in = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0]
    L_out = cv2.cvtColor(scurve_L(img), cv2.COLOR_BGR2LAB)[..., 0]
    ink = L_in < 128

    assert np.median(L_out[ink]) < np.median(L_in[ink])
    assert np.median(L_out[~ink]) > np.median(L_in[~ink])


def test_unsharp_increases_edge_gradient():
    # Soft step edge, blurred to guarantee a low starting gradient.
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, 50:] = 200
    img = cv2.GaussianBlur(img, (0, 0), sigmaX=3.0)

    gray_before = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_after = cv2.cvtColor(unsharp_L(img), cv2.COLOR_BGR2GRAY)

    grad_before = np.abs(cv2.Sobel(gray_before, cv2.CV_32F, 1, 0)).max()
    grad_after = np.abs(cv2.Sobel(gray_after, cv2.CV_32F, 1, 0)).max()

    assert grad_after > grad_before


def test_enhance_document_end_to_end():
    img = _add_text_lines(_paper_with_shadow())
    out = enhance_document(img)

    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert not np.isnan(out).any()


def test_enhance_document_handles_blank_image():
    img = np.full((80, 80, 3), 128, dtype=np.uint8)
    out = enhance_document(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_enhance_document_writes_debug_stages(tmp_path):
    from docprep.debug import DebugWriter

    dbg = DebugWriter(tmp_path)
    enhance_document(_add_text_lines(_paper_with_shadow()), debug=dbg)

    for name in ("03_flattened", "04_balanced", "05_whitepoint", "06_scurve", "07_unsharp"):
        assert (tmp_path / f"{name}.jpg").exists()
