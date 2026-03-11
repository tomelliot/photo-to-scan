"""Wrapper around scan_document for easy mocking in tests."""

import numpy as np


def run_scan(image: np.ndarray) -> np.ndarray:
    from docprep.scan import scan_document
    return scan_document(image)
