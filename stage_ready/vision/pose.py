"""Did the pose track follow ONE person, of a steady size, all the way through?

Pose *coverage* — the fraction of frames where somebody was found — is the wrong question.
`sandy_hackett_v2.mp4` scored 100 % coverage while 20 % of its frames tracked a phantom read out
of a reflection in a glass door, and nothing in the run said a word. So three better questions,
all answered off the pose alone, before anything expensive has run:

  1. Was it the same person?   frames whose subject size or body centre is far from the
                               clip's median are off-subject            → `one_subject`
  2. Did they stay put?        p95/p5 of a smoothed body ruler            → `distance_steady`
  3. How big are they?         the ruler's median as a fraction of picture height, and the
                               shoulder span as a fraction of the canvas  → `subject_size`

Port of the archive's `tools/pose_qc.py`. The pose itself comes from a body-pose tracker (Apple
Vision's `BodyTrack` in the archive; the CSV is the contract) — this measures the track, and
the thresholds are the profile's, applied by the caller.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from math import isfinite, nan


def read_pose(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class PoseQC:
    frames: int
    coverage: float               # fraction of frames with a pose
    one_subject: float            # fraction of frames on the same subject
    off_subject: int
    off_by_size: int
    off_by_position: int
    subject_height: float         # median body ruler / picture height (nan if unmeasurable)
    drift: float                  # apparent size p95 / p5 (nan if unmeasurable)
    shoulder_span_p50: float      # shoulder span / picture width, raw frames (nan if unmeasurable)
    shoulder_span_p95: float
    picture: tuple[int, int]


def _col(rows, name, np):
    a = np.full(len(rows), np.nan)
    for i, r in enumerate(rows):
        v = r.get(name, "")
        if v not in ("", None):
            try:
                a[i] = float(v)
            except ValueError:
                pass
    return a


def _mean_of(rows, np, *names):
    st = np.vstack([_col(rows, n, np) for n in names])
    seen = np.isfinite(st)
    return np.where(seen.any(axis=0),
                    np.where(seen, st, 0.0).sum(axis=0) / np.maximum(seen.sum(axis=0), 1),
                    np.nan)


def pose_qc(rows: list[dict], size_tol: float = 2.0, centre_tol: float = 0.20) -> PoseQC:
    import numpy as np

    if not rows:
        raise ValueError("pose_qc: empty pose csv")
    N = len(rows)
    W = float(rows[0].get("w") or 1)
    H = float(rows[0].get("h") or 1)

    found = np.array([r.get("found") == "1" for r in rows])
    cov = float(found.mean())

    # ---- 1. same person
    size = _col(rows, "size", np)
    size[size <= 0] = np.nan
    cx = _mean_of(rows, np, "shL_x", "shR_x", "hipL_x", "hipR_x")
    msize = float(np.nanmedian(size)) if np.isfinite(size).any() else nan
    mcx = float(np.nanmedian(cx)) if np.isfinite(cx).any() else nan
    bad_size = np.zeros(N, bool)
    if isfinite(msize) and msize > 0:
        bad_size = np.isfinite(size) & ((size < msize / size_tol) | (size > msize * size_tol))
    bad_cx = np.zeros(N, bool)
    if isfinite(mcx):
        bad_cx = np.isfinite(cx) & (np.abs(cx - mcx) > centre_tol * W)
    bad = bad_size | bad_cx

    # ---- 2. steady distance — a body ruler, not a bounding box: the shoulder span if both
    # shoulders are visible, else the eye-to-shoulder drop scaled to match it. Both are rigid,
    # so neither moves when the arms do.
    span = np.abs(_col(rows, "shL_x", np) - _col(rows, "shR_x", np))
    drop = np.abs(_mean_of(rows, np, "shL_y", "shR_y") - _mean_of(rows, np, "eyeL_y", "eyeR_y", "nose_y")) * 2.6
    scale = np.where(np.isfinite(span), span, drop)
    ok = np.isfinite(scale)
    drift = med_scale = nan
    if ok.sum() >= max(8, 0.3 * N):
        idx = np.arange(N)
        s = np.interp(idx, idx[ok], scale[ok])
        k = np.ones(15) / 15.0                       # ~half a second, to take out pose jitter
        s = np.convolve(np.pad(s, 7, mode="reflect"), k, mode="valid")
        p5, med_scale, p95 = (float(v) for v in np.percentile(s, [5, 50, 95]))
        drift = p95 / max(p5, 1e-6)

    sp50 = sp95 = nan
    if np.isfinite(span).any():
        sp50, sp95 = (float(v) / W for v in np.nanpercentile(span, [50, 95]))

    return PoseQC(frames=N, coverage=cov, one_subject=float(1.0 - bad.mean()), off_subject=int(bad.sum()),
                  off_by_size=int(bad_size.sum()), off_by_position=int(bad_cx.sum()),
                  subject_height=(med_scale / H) if isfinite(med_scale) else nan, drift=drift,
                  shoulder_span_p50=sp50, shoulder_span_p95=sp95, picture=(int(W), int(H)))
