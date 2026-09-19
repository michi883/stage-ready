"""How far the performer stands out from the stage, in luminance alone.

A performer is separated from the curtain by three things: brightness, hue, and the rim and
light wrap the grade puts on their edge. Only the first survives a small screen, a heavy
re-encode, a greyscale thumbnail, or a viewer with reduced colour vision — so it is the one
worth a number, and the one the profile gates (`separation` ≥ 1.5).

`ethel_chadwick_v2.mp4` is why this exists: a red trouser suit 12° of hue and 14 % of luma from
the curtain. In colour the delivery reads well; in luminance her jacket merges into the
background and only her face, collar and hands carry the silhouette.

Measured just inside and just outside the alpha edge, on the finished composite — one 9-px ring
each side: far enough out to clear the feather, close enough in that it is still the performer
and still the curtain right behind them. BT.709 luma, median per frame, mean over the sampled
frames, ratio of the brighter side to the darker.

Port of the archive's `tools/silhouette_qc.py`. The composite can be a directory of frames or
the delivered video itself — the delivery is what a viewer sees, and decoding it with OpenCV
keeps the measurement on the file that ships.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

from . import require_cv2


@dataclass
class Separation:
    inside: float                 # mean of per-frame median luma, ring just inside the edge
    outside: float                # … just outside
    ratio: float                  # max / min of the two
    frames: int                   # frames that contributed
    source: str                   # what was measured: the directory or the video file


def _frames_from_dir(comp_dir, idx, cv2):
    comps = sorted(glob.glob(os.path.join(comp_dir, "*.png")))
    for i in idx:
        if i < len(comps):
            yield i, cv2.imread(comps[i])


def _frames_from_video(path, idx, cv2):
    # Sequential decode, keeping the wanted frames: seeking H.264 by frame number lands on the
    # nearest keyframe in too many containers to trust for a measurement.
    want = set(int(i) for i in idx)
    cap = cv2.VideoCapture(str(path))
    n = 0
    last = max(want) if want else -1
    while n <= last:
        ok, im = cap.read()
        if not ok:
            break
        if n in want:
            yield n, im
        n += 1
    cap.release()


def separation(composite: str, matte_dir: str, nsamp: int = 24) -> Separation:
    cv2 = require_cv2()
    import numpy as np

    BT709 = np.array([0.0722, 0.7152, 0.2126])          # BGR, as OpenCV loads
    mattes = sorted(glob.glob(os.path.join(matte_dir, "*.png")))
    if os.path.isdir(composite):
        n_comp = len(glob.glob(os.path.join(composite, "*.png")))
        n = min(n_comp, len(mattes))
    else:
        n = len(mattes)
    if n == 0:
        raise ValueError("separation: nothing to measure")
    idx = np.linspace(0, n - 1, min(nsamp, n)).astype(int)
    frames = _frames_from_dir(composite, idx, cv2) if os.path.isdir(composite) else _frames_from_video(composite, idx, cv2)

    k = np.ones((9, 9), np.uint8)
    inner_l, outer_l = [], []
    for i, c in frames:
        a = cv2.imread(mattes[i], cv2.IMREAD_GRAYSCALE)
        if a is None or c is None:
            continue
        if a.shape[:2] != c.shape[:2]:
            raise ValueError(f"separation: matte {a.shape[:2]} and composite {c.shape[:2]} differ in size on frame {i + 1}")
        body = (a > 200).astype(np.uint8)
        inner = (cv2.erode(body, k, iterations=1).astype(bool) ^ cv2.erode(body, k, iterations=2).astype(bool))
        outer = (cv2.dilate(body, k, iterations=2).astype(bool) ^ cv2.dilate(body, k, iterations=1).astype(bool))
        if inner.sum() < 200 or outer.sum() < 200:
            continue
        lum = c.astype(np.float32) / 255.0 @ BT709
        inner_l.append(float(np.median(lum[inner])))
        outer_l.append(float(np.median(lum[outer])))
    if not inner_l:
        raise ValueError("separation: could not sample the silhouette edge")

    i_m, o_m = float(np.mean(inner_l)), float(np.mean(outer_l))
    ratio = max(i_m, o_m) / max(1e-6, min(i_m, o_m))
    return Separation(inside=i_m, outside=o_m, ratio=ratio, frames=len(inner_l), source=str(composite))
