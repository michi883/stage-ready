"""Is the matte actually holding the whole performer?

Every other gate is a count, a hash or a consistency test: they prove the run did what it said,
not that the alpha is any good. That gap let `sandy_hackett_v2.mp4` ship with a quarter of the
performer's hair missing — the matte was complete, stamped, self-consistent, and wrong.

This measures the matte against a second opinion: an independent silhouette on a handful of
frames spread through the clip (Apple Vision's `PersonMatte` in the archive; the OpenCV 5 DNN
`SubjectSegmenter` is what replaces it — README, roadmap milestone 8). The opinion is coarser
than the matte at an edge, but it is independent, and it is very hard for both to lose the same
100 px of hair. Only the head band is compared: hands and clothing move between two models'
ideas of the subject; the top of the head is where a shrink-wrapped matte shows itself.

The opinion's raw output is not the comparison. It segments every person-shaped thing in the
room — on Sandy that includes a figure read out of a reflection — so the same component cleanup
the seed gets is applied first: keep the components the pose is standing in, plus the largest.

Port of the archive's `tools/matte_qc.py`.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass

from . import require_cv2

JOINTS = ("nose", "eyeL", "eyeR", "earL", "earR", "neck", "shL", "shR")


@dataclass
class MatteQC:
    median: float                 # matte head width / opinion head width, median over frames
    frames: int                   # frames compared
    worst_frame: int
    worst_matte_px: int
    worst_opinion_px: int
    ratios: list[float]


def _performer(v, n, pose, thresh, cv2, np):
    """The opinion's alpha reduced to the performer, the way clean_seed.py reduces the seed."""
    nc, lab, stats, _ = cv2.connectedComponentsWithStats((v > thresh).astype(np.uint8), 8)
    if nc <= 1:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = {int(np.argmax(areas)) + 1}
    row = pose[n - 1] if 0 < n <= len(pose) else None
    if row is not None:
        for j in JOINTS:
            try:
                x, y = float(row.get(f"{j}_x", "")), float(row.get(f"{j}_y", ""))
            except (TypeError, ValueError):
                continue
            yi, xi = int(round(y)), int(round(x))
            near = lab[max(0, yi - 3):yi + 4, max(0, xi - 3):xi + 4]
            near = near[near > 0]
            if near.size:
                keep.add(int(np.bincount(near).argmax()))
    return np.isin(lab, sorted(keep))


def head_band_widths(matte_gray, opinion_bool, thresh: int = 32) -> "tuple[int, int] | None":
    """(matte head width, opinion head width) in px over the head band — the top quarter of the
    opinion's silhouette, at least 40 rows. None when the opinion is too small to compare."""
    import numpy as np
    ys = np.where(opinion_bool.any(1))[0]
    if not len(ys):
        return None
    band = slice(ys.min(), ys.min() + max(40, int(0.25 * (opinion_bool.shape[0] - ys.min()))))
    wa = int((matte_gray[band] > thresh).any(0).sum())
    wb = int(opinion_bool[band].any(0).sum())
    return (wa, wb) if wb >= 20 else None


def performer_component(alpha, pose_row: dict | None, thresh: int = 32):
    """An opinion's alpha reduced to the performer: the connected components the pose is standing in,
    plus the largest — the cleanup `clean_seed.py` does before a seed is propagated."""
    cv2 = require_cv2()
    import numpy as np
    return _performer(alpha, 1, [pose_row] if pose_row else [], thresh, cv2, np)


def matte_extent(matte_dir: str, opinion_dir: str, pose: list[dict], thresh: int = 32) -> MatteQC:
    cv2 = require_cv2()
    import numpy as np

    mattes = sorted(glob.glob(os.path.join(matte_dir, "f_*.png")))
    opinions = sorted(glob.glob(os.path.join(opinion_dir, "f_*.png")))
    if not mattes or not opinions:
        raise ValueError("matte_extent: nothing to compare")

    ratios, rows = [], []
    for v in opinions:
        n = int(re.search(r"f_(\d+)", os.path.basename(v)).group(1))
        if n > len(mattes):
            continue
        a = cv2.imread(mattes[n - 1], cv2.IMREAD_GRAYSCALE)
        b = cv2.imread(v, cv2.IMREAD_GRAYSCALE)
        if a is None or b is None or a.shape != b.shape:
            continue
        clean = _performer(b, n, pose, thresh, cv2, np)
        if clean is None or not clean.any():
            continue
        w = head_band_widths(a, clean, thresh)
        if w is None:
            continue
        wa, wb = w
        ratios.append(wa / wb)
        rows.append((n, wa, wb))
    if not ratios:
        raise ValueError("matte_extent: no comparable frames")

    worst = min(rows, key=lambda r: r[1] / r[2])
    return MatteQC(median=float(np.median(ratios)), frames=len(ratios), worst_frame=worst[0],
                   worst_matte_px=worst[1], worst_opinion_px=worst[2], ratios=[float(r) for r in ratios])


def crown_cut(matte_dir: str, thresh: int = 16) -> float:
    """Fraction of frames on which the silhouette touches the top row of the picture — the crown
    was never recorded there, and no downstream step can put it back."""
    cv2 = require_cv2()
    mattes = sorted(glob.glob(os.path.join(matte_dir, "f_*.png")))
    if not mattes:
        raise ValueError("crown_cut: no mattes")
    cut = 0
    for f in mattes:
        m = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        if m is not None and (m[0] > thresh).any():
            cut += 1
    return cut / len(mattes)
