"""Tests for docprep.enhance: each stage + end-to-end."""

import cv2
import numpy as np
import pytest

from docprep.enhance import (
    apply_clahe_L,
    balance_white,
    enhance_document,
    flatten_illumination,
    stretch_contrast_L,
    unsharp_L,
)


def _paper_with_shadow(h: int = 240, w: int = 240, base: int = 220) -> np.ndarray:
    """Uniform paper (BGR = base) darkened by a left-to-right illumination ramp."""
    ramp = np.linspace(0.5, 1.0, w, dtype=np.float32)[None, :, None]
    img = np.full((h, w, 3), base, dtype=np.float32) * ramp
    return np.clip(img, 0, 255).astype(np.uint8)


def test_flatten_illumination_removes_gradient():
    img = _paper_with_shadow()

    before = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].mean(axis=0)
    after = cv2.cvtColor(flatten_illumination(img), cv2.COLOR_BGR2LAB)[..., 0].mean(axis=0)

    assert after.std() < before.std() * 0.5


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


def test_stretch_contrast_expands_range():
    # Gradient in a compressed luminance range.
    gradient = np.linspace(80, 160, 256, dtype=np.uint8)
    img = np.repeat(gradient[None, :], 64, axis=0)
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    out = stretch_contrast_L(img)
    L_out = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)[..., 0]

    assert L_out.min() < 10
    assert L_out.max() > 245


def test_clahe_preserves_shape_and_dtype():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
    out = apply_clahe_L(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


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
    img = _paper_with_shadow()
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
    enhance_document(_paper_with_shadow(), debug=dbg)

    for name in ("03_flattened", "04_balanced", "05_stretched", "06_clahe", "07_unsharp"):
        assert (tmp_path / f"{name}.jpg").exists()
