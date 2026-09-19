"""The two grade values that are properties of the *recording*, not of the look.

Everything else in the grade describes the stage and is the same for every clip. These two
describe the room the performer filmed in, and typing them per clip is exactly the manual
tuning the loop exists to remove:

    key side       which side the light comes from — the brightness difference between the two
                   halves of the silhouette. The stage's key falloff and rim follow it, or the
                   performer reads as lit by two contradictory lamps         → `key_direction`
    face exposure  how bright the performer needs to be to sit on a lit stage, measured off the
                   face and clamped hard, because this is the parameter that would do the most
                   damage if the measurement were ever wrong               → `face_exposure`

Port of the archive's `tools/auto_grade.py`. Reads the source frames, the matte and the pose.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from math import nan

from . import require_cv2


@dataclass
class GradeQC:
    left: float                   # median silhouette luma, left half
    right: float
    ratio: float                  # right / left; below ~8 % either way the room is flat-lit
    keydx: int
    face: float                   # median face luma (nan if no face patch)
    gain: float                   # the lift the face asked for
    fgexp: float                  # the lift applied, inside the clamp
    clamped: bool
    frames: int


def _fnum(r, k, np):
    try:
        return float(r.get(k, ""))
    except (TypeError, ValueError):
        return np.nan


def grade_qc(band_dir: str, matte_dir: str, pose: list[dict], face_target: float = 0.46,
             clamp: tuple[float, float] = (0.80, 1.25), nsamp: int = 48) -> GradeQC:
    cv2 = require_cv2()
    import numpy as np

    from . import frame_number, sample_indices

    BT709 = np.array([0.0722, 0.7152, 0.2126])
    bands = {frame_number(f): f for f in glob.glob(os.path.join(band_dir, "*.jpg")) + glob.glob(os.path.join(band_dir, "*.png"))}
    mattes = sorted(glob.glob(os.path.join(matte_dir, "*.png")))
    n = min(len(mattes), len(pose))                     # the matte and pose are complete; the source frames may be sampled
    if n == 0 or not bands:
        raise ValueError("grade_qc: nothing to measure")
    idx = sample_indices(n, nsamp)

    face_lum, dL, dR = [], [], []
    for i in idx:
        if bands.get(i + 1) is None:
            continue
        im = cv2.imread(bands[i + 1])
        mt = cv2.imread(mattes[i], cv2.IMREAD_GRAYSCALE)
        if im is None or mt is None:
            continue
        im = im.astype(np.float32) / 255.0
        if mt.shape[:2] != im.shape[:2]:
            mt = cv2.resize(mt, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_LINEAR)
        lum = im @ BT709
        body = mt > 160
        if body.sum() < 500:
            continue
        r = pose[i]
        with np.errstate(invalid="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                hx = np.nanmean([_fnum(r, k, np) for k in ("nose_x", "eyeL_x", "eyeR_x", "earL_x", "earR_x")])
                hy = np.nanmean([_fnum(r, k, np) for k in ("nose_y", "eyeL_y", "eyeR_y")])
                bx = np.nanmean([_fnum(r, k, np) for k in ("shL_x", "shR_x", "hipL_x", "hipR_x")])
        ew = np.abs(_fnum(r, "earL_x", np) - _fnum(r, "earR_x", np))
        if not np.isfinite(ew):
            ew = np.abs(_fnum(r, "eyeL_x", np) - _fnum(r, "eyeR_x", np)) * 2.4
        if np.isfinite(hx) and np.isfinite(hy) and np.isfinite(ew) and ew > 4:
            h = int(ew * 0.45)
            y0, y1 = int(max(0, hy - h)), int(min(lum.shape[0], hy + h))
            x0, x1 = int(max(0, hx - h)), int(min(lum.shape[1], hx + h))
            patch, pm = lum[y0:y1, x0:x1], body[y0:y1, x0:x1]
            if pm.sum() > 50:
                face_lum.append(float(np.median(patch[pm])))
        if not np.isfinite(bx):
            xs = np.flatnonzero(body.any(axis=0))
            bx = 0.5 * (xs.min() + xs.max())
        c = int(bx)
        L = body.copy(); L[:, c:] = False
        R = body.copy(); R[:, :c] = False
        if L.sum() > 500 and R.sum() > 500:
            dL.append(float(np.median(lum[L])))
            dR.append(float(np.median(lum[R])))
    if not dL:
        raise ValueError("grade_qc: could not measure the silhouette")

    left, right = float(np.median(dL)), float(np.median(dR))
    ratio = right / max(left, 1e-4)
    keydx = 1 if ratio > 1.08 else -1               # flat-lit keeps the stage's own convention
    if face_lum:
        face = float(np.median(face_lum))
        gain = (face_target / max(face, 1e-3)) ** 2.2   # exposureAdjust is linear-light; the read is sRGB
        fgexp = float(np.clip(gain, *clamp))
        clamped = abs(gain - fgexp) > 1e-6
    else:
        face, gain, fgexp, clamped = nan, 1.0, 1.0, False
    return GradeQC(left=left, right=right, ratio=ratio, keydx=keydx, face=face, gain=gain,
                   fgexp=fgexp, clamped=clamped, frames=len(dL))
