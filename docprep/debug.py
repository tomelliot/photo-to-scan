"""Debug output for pipeline stages."""

from pathlib import Path

import cv2
import numpy as np


class DebugWriter:
    """Writes intermediate pipeline images to a debug directory.

    When disabled (the default), all write calls are no-ops.
    """

    def __init__(self, output_dir: Path | None = None, prefix: str = ""):
        self._dir = output_dir
        self._prefix = prefix
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._dir is not None

    def write(self, name: str, image: np.ndarray) -> None:
        if self._dir is None:
            return
        filename = f"{self._prefix}{name}.jpg" if self._prefix else f"{name}.jpg"
        cv2.imwrite(str(self._dir / filename), image)

    def write_contours(
        self, name: str, image: np.ndarray, contours: list[np.ndarray]
    ) -> None:
        """Draw contours on a copy of the image and write it."""
        if self._dir is None:
            return
        vis = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(vis, contours, -1, (0, 255, 0), 2)
        self.write(name, vis)

    def write_quad(
        self, name: str, image: np.ndarray, quad: np.ndarray | None
    ) -> None:
        """Draw a quadrilateral on a copy of the image and write it."""
        if self._dir is None or quad is None:
            return
        vis = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        pts = quad.reshape(4, 2).astype(np.int32)
        cv2.polylines(vis, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
        for pt in pts:
            cv2.circle(vis, tuple(pt), 5, (0, 255, 0), -1)
        self.write(name, vis)
