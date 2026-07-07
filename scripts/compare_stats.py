"""L-channel stats for every method, per example."""
from pathlib import Path
import cv2
import numpy as np

OUT = Path("ablation_out")
files_by_doc: dict[str, list[Path]] = {}
for p in sorted(OUT.glob("example_*.jpg")):
    doc = p.stem.split("_")[1]
    files_by_doc.setdefault(doc, []).append(p)

for doc, paths in files_by_doc.items():
    print(f"\nexample_{doc}")
    for p in paths:
        img = cv2.imread(str(p))
        L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0]
        pct = np.percentile(L, [1, 10, 50, 90, 99])
        variant = p.stem.split(f"_{doc}_", 1)[-1]
        print(f"  {variant:<14} mean={L.mean():6.1f}  p1/10/50/90/99={pct[0]:3.0f}/{pct[1]:3.0f}/{pct[2]:3.0f}/{pct[3]:3.0f}/{pct[4]:3.0f}")
