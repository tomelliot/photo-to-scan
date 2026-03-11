"""Document scanning: detect corners, perspective crop, deskew.

Uses DocAligner (DocsaidLab) heatmap regression model for corner detection.
"""

from pathlib import Path

import cv2
import numpy as np

from docprep.debug import DebugWriter
from docprep.deskew import deskew_image


def _get_model():
    """Lazily create and cache the DocAligner model."""
    if not hasattr(_get_model, "_model"):
        from docaligner import DocAligner

        _get_model._model = DocAligner()
    return _get_model._model


def _perspective_crop(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Warp document region to a rectangle using 4 corner points."""
    pts = corners.astype(np.float32)

    w_top = np.linalg.norm(pts[1] - pts[0])
    w_bot = np.linalg.norm(pts[2] - pts[3])
    width = int(max(w_top, w_bot))

    h_left = np.linalg.norm(pts[3] - pts[0])
    h_right = np.linalg.norm(pts[2] - pts[1])
    height = int(max(h_left, h_right))

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(image, M, (width, height))


def scan_document(
    image: np.ndarray,
    debug_dir: Path | None = None,
    debug_prefix: str = "",
) -> np.ndarray:
    """Detect, crop, and deskew a document from a photo.

    Returns the cropped and deskewed document, or the original image
    if no document is detected.
    """
    dbg = DebugWriter(debug_dir, debug_prefix)
    dbg.write("00_input", image)

    model = _get_model()
    polygon = model(image)

    if polygon is None or len(polygon) == 0:
        return image

    corners = polygon.astype(np.float32)
    dbg.write_quad("01_quad", image, corners.reshape(4, 1, 2).astype(np.int32))

    cropped = _perspective_crop(image, corners)
    dbg.write("02_cropped", cropped)

    result = deskew_image(cropped)
    dbg.write("99_final", result)
    return result
