"""Post-crop deskew: correct residual rotation using Hough-based skew detection."""

import cv2
import numpy as np
from deskew import determine_skew


def deskew_image(image: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Detect and correct skew in a cropped document image.

    Only corrects angles up to max_angle degrees — larger rotations suggest
    the detection is unreliable.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    angle = determine_skew(gray)

    if angle is None or abs(angle) > max_angle:
        return image

    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Compute new bounding size to avoid clipping corners
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    return cv2.warpAffine(image, M, (new_w, new_h), borderValue=(255, 255, 255))
