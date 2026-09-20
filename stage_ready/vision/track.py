"""Where the head sits on the delivered canvas, frame by frame.

The reframe solve (`track_frame.py` in the archive: uniform scale + translation per frame, the
slow drift cancelled, the performance kept) promises one thing above all: the head stays at the
same height on the stage. Two gates hold it to that —

    head_spread   p95 − p5 of the head's height on the canvas, as a fraction of canvas height
    head_drift    the same spread after the fast part is removed, in canvas pixels: motion slower
                  than `drift_sec` is drift, and drift is what the solve exists to cancel

Both need the head top per source frame, which the solve reads from the matte inside the pose's
head column (so hair is included and a raised hand is not — a matte bounding box would follow a
fingertip), and the solved transform from `affine.csv`. This is that read, ported from the matte
pass of `track_frame.py`, applied through the archived transform.
"""
from __future__ import annotations

import csv
import glob
import os
from dataclasses import dataclass

from . import require_cv2


@dataclass
class HeadHeight:
    frames: int
    head_out: list[float]         # per-frame head height on the canvas, fraction of canvas height
    spread: float                 # p95 − p5 of head_out
    drift_px: float               # p95 − p5 of the slow part of head_out, in canvas px
    head_median: float            # where the head actually sits
    source_spread: float          # p95 − p5 of the head top in the source, fraction of picture height
    scale_median: float


def _col(rows, name, np):
    out = np.full(len(rows), np.nan)
    for i, r in enumerate(rows):
        v = r.get(name, "")
        if v not in ("", None):
            try:
                out[i] = float(v)
            except ValueError:
                pass
    return out


def _nanmean_cols(np, *cols):
    a = np.vstack(cols)
    with np.errstate(invalid="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmean(a, axis=0)


def _fill(x, np):
    x = np.asarray(x, dtype=np.float64)
    ok = np.isfinite(x)
    if not ok.any():
        return x
    idx = np.arange(len(x))
    return np.interp(idx, idx[ok], x[ok])


def _smooth(x, sigma, np):
    if sigma < 0.51 or len(x) < 3:
        return x.astype(np.float64).copy()
    r = int(max(1, round(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(x.astype(np.float64), r, mode="reflect")
    return np.convolve(pad, k, mode="valid")


@dataclass
class Anchors:
    top: list[float]              # head top per frame, source px, read inside the pose's head column
    bot: list[float]              # silhouette bottom per frame, source px
    cutoff: list[bool]            # the frame bottom cuts the silhouette (the standing-performer case)
    body_x: list[float]
    picture_w: int
    picture_h: int


def anchors(matte_dir: str, pose: list[dict]) -> Anchors:
    """The per-frame anchors the solve is built on, read from the matte and the pose. The
    picture size is taken from the mattes themselves (the crown-completed picture, where the
    archive extended it)."""
    cv2 = require_cv2()
    import numpy as np

    files = sorted(glob.glob(os.path.join(matte_dir, "*.png")))
    N = len(pose)
    if len(files) != N:
        raise ValueError(f"head_top: {len(files)} mattes vs {N} pose rows")
    first = cv2.imread(files[0], cv2.IMREAD_GRAYSCALE)
    BH, BW = (float(v) for v in first.shape[:2])

    nose_x, eyeL_x, eyeR_x, earL_x, earR_x = (_col(pose, k, np) for k in ("nose_x", "eyeL_x", "eyeR_x", "earL_x", "earR_x"))
    shL_x, shR_x, hipL_x, hipR_x = (_col(pose, k, np) for k in ("shL_x", "shR_x", "hipL_x", "hipR_x"))
    head_x = _nanmean_cols(np, nose_x, eyeL_x, eyeR_x, earL_x, earR_x)
    body_x = _nanmean_cols(np, shL_x, shR_x, hipL_x, hipR_x)
    ear_w = np.abs(earL_x - earR_x)
    eye_w = np.abs(eyeL_x - eyeR_x) * 2.4
    sh_w = np.abs(shL_x - shR_x) * 0.42
    head_w = np.where(np.isfinite(ear_w), ear_w, np.where(np.isfinite(eye_w), eye_w, sh_w))
    head_x, body_x, head_w = _fill(head_x, np), _fill(body_x, np), _fill(head_w, np)
    if not np.isfinite(head_w).any():
        head_w = np.full(N, 0.10 * BW)
    if not np.isfinite(body_x).any():
        body_x = np.full(N, BW / 2.0)
    if not np.isfinite(head_x).any():
        head_x = body_x.copy()

    top = np.full(N, np.nan)
    bot = np.full(N, np.nan)
    cutoff = np.zeros(N, dtype=bool)
    for i, f in enumerate(files):
        # Half resolution, as the solve reads it: 2 px of read precision is far below the noise
        # floor once the anchors are smoothed over a second.
        m = cv2.imread(f, cv2.IMREAD_REDUCED_GRAYSCALE_2)
        if m is None:
            continue
        sy, sx = BH / m.shape[0], BW / m.shape[1]
        b = m > 128
        if not b.any():
            continue
        rowsum = b.sum(axis=1)
        ys = np.flatnonzero(rowsum)
        bot[i] = (ys.max() + 1) * sy
        cutoff[i] = rowsum[-1] * sx > 0.01 * BW
        hw = max(head_w[i], 0.05 * BW)
        x0 = int(max(0, (head_x[i] - 0.95 * hw) / sx))
        x1 = int(min(m.shape[1], (head_x[i] + 0.95 * hw) / sx + 1))
        band = b[:, x0:x1] if x1 > x0 else b
        hy = np.flatnonzero(band.sum(axis=1) >= 2)
        top[i] = (hy.min() if len(hy) else ys.min()) * sy
    if not np.isfinite(top).any():
        raise ValueError("anchors: matte is empty on every frame")
    return Anchors(top=[float(v) for v in _fill(top, np)], bot=[float(v) for v in _fill(bot, np)],
                   cutoff=[bool(v) for v in cutoff], body_x=[float(v) for v in body_x],
                   picture_w=int(BW), picture_h=int(BH))


@dataclass
class DrySolve:
    """What the framing rule would do to this clip, before anything is rendered: how wide the
    performer comes out on the canvas at the profile's head target, and where the head has to
    go to hold the size cap. Port of the size-cap block of `track_frame.py`; the transform
    itself is not solved here."""
    head_target: float            # the profile's floor
    head_target_used: float       # after the cap — equal to the floor for a to-spec recording
    span_p50: float               # the subject-size ruler / canvas width at the floor: the shoulder span,
    span_p95: float               #   smoothed over 0.5 s, the eye-to-shoulder drop standing in where the
    span_p50_used: float          #   shoulders are not seen — ONE ruler, the same the cap is solved on,
    span_p95_used: float          #   so the gate reads exactly what the fix promised (p95_used == cap when capped)
    widest: float                 # == span_p95: kept for the fixtures and the fix's wording
    scale_median: float           # at head_target_used
    cut_frac: float               # frames on which the frame bottom cuts the silhouette
    frames: int


def dry_solve(matte_dir: str, pose: list[dict], canvas: tuple[int, int], fps: float, head_target: float = 0.334,
              stab_sec: float = 1.25, size_cap: float = 0.55, head_target_max: float = 0.55) -> DrySolve:
    import numpy as np

    a = anchors(matte_dir, pose)
    OW, OH = (float(v) for v in canvas)
    BW, BH = float(a.picture_w), float(a.picture_h)
    N = len(a.top)
    top, bot, cutoff = np.asarray(a.top), np.asarray(a.bot), np.asarray(a.cutoff)
    subj_bot = _smooth(np.where(cutoff, BH, bot), 0.25 * fps, np)
    sigma = stab_sec * fps
    height_s = np.maximum(_smooth(subj_bot, sigma, np) - _smooth(top, sigma, np), 8.0)
    s0 = OH * (1.0 - head_target) / height_s

    span = np.abs(_col(pose, "shL_x", np) - _col(pose, "shR_x", np))
    drop = np.abs(_nanmean_cols(np, _col(pose, "shL_y", np), _col(pose, "shR_y", np)) -
                  _nanmean_cols(np, _col(pose, "eyeL_y", np), _col(pose, "eyeR_y", np), _col(pose, "nose_y", np))) * 2.6
    ruler = np.where(np.isfinite(span), span, drop)
    used, widest, shrink = head_target, float("nan"), 1.0
    if np.isfinite(ruler).sum() >= max(8, 0.3 * N):
        ruler_s = _smooth(_fill(ruler, np), 0.5 * fps, np)
        widest = float(np.percentile(ruler_s * s0, 95)) / OW
        if widest > size_cap:
            shrink = size_cap / widest
            med_h = float(np.median(height_s))
            used = float(np.clip(1.0 - med_h * np.median(s0) * shrink / OH, head_target, head_target_max))
    s_used = OH * (1.0 - used) / height_s
    # The size the gate reads is the size the cap was solved on: the same smoothed ruler, at the
    # floor and at the head target actually used. (Reading the raw per-frame shoulder span here
    # instead — as this did until 2026-09-20 — put a capped close-up 0.3 % over the cap the fix
    # had just promised; the evaluation caught it.)
    if np.isfinite(widest):
        p50, p95 = (float(v) / OW for v in np.percentile(ruler_s * s0, [50, 95]))
        q50, q95 = (float(v) / OW for v in np.percentile(ruler_s * s_used, [50, 95]))
    else:                                            # too few frames carry a ruler: report what the raw span says
        ok = np.isfinite(span)
        p50, p95 = (float(v) / OW for v in np.percentile(span[ok] * s0[ok], [50, 95])) if ok.any() else (float("nan"),) * 2
        q50, q95 = (float(v) / OW for v in np.percentile(span[ok] * s_used[ok], [50, 95])) if ok.any() else (float("nan"),) * 2
        widest = p95
    return DrySolve(head_target=head_target, head_target_used=used, span_p50=p50, span_p95=p95,
                    span_p50_used=q50, span_p95_used=q95, widest=widest, scale_median=float(np.median(s_used)),
                    cut_frac=float(cutoff.mean()), frames=N)


def read_affine(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def head_height(matte_dir: str, pose: list[dict], affine: list[dict], canvas_h: int,
                fps: float, drift_sec: float = 2.0) -> HeadHeight:
    import numpy as np

    a = anchors(matte_dir, pose)
    top, BH = np.asarray(a.top), float(a.picture_h)
    if len(affine) != len(top):
        raise ValueError(f"head_height: {len(affine)} transforms vs {len(top)} frames")
    scale = np.array([float(r["scale"]) for r in affine])
    ty = np.array([float(r["ty"]) for r in affine])
    head_out = (ty + top * scale) / canvas_h
    p5, p95 = np.percentile(head_out, [5, 95])
    slow = _smooth(head_out, drift_sec * fps, np) * canvas_h
    s5, s95 = np.percentile(slow, [5, 95])
    src5, src95 = np.percentile(top, [5, 95])
    return HeadHeight(frames=len(top), head_out=[float(v) for v in head_out], spread=float(p95 - p5),
                      drift_px=float(s95 - s5), head_median=float(np.median(head_out)),
                      source_spread=float((src95 - src5) / BH), scale_median=float(np.median(scale)))
