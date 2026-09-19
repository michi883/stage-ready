"""The two gates that are not about the picture at all, and the facts INSPECT states up front.

    frame_count   every source frame is rendered, so the delivery has exactly as many frames as
                  the source — counted by decoding, not read from a header that may be an estimate
    audio_md5     the delivery carries the source's audio stream untouched: the decoded audio
                  hashes identically. Pipelines that trim with `-shortest` lose the last packet;
                  this is how that was caught.

`probe` reads the container facts (size, fps, frame count as the header states it, duration)
with OpenCV. The audio hash needs ffmpeg — OpenCV does not decode audio — and is the one
subprocess in this package.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from . import require_cv2


@dataclass
class Probe:
    width: int
    height: int
    fps: float
    frames_declared: int          # what the container says; `frame_count` counts for real
    duration_s: float


def probe(path: str) -> Probe:
    cv2 = require_cv2()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"probe: cannot open {path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return Probe(width=w, height=h, fps=fps, frames_declared=n, duration_s=(n / fps) if fps else 0.0)


def frame_count(path: str) -> int:
    """Decoded frames, counted — the number ffprobe -count_frames gives."""
    cv2 = require_cv2()
    cap = cv2.VideoCapture(str(path))
    n = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        n += 1
    cap.release()
    return n


def audio_md5(path: str) -> str:
    """MD5 of the decoded audio stream, as `ffmpeg -map 0:a -f md5` reports it."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("audio_md5: ffmpeg is not on PATH")
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a", "-f", "md5", "-"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out.removeprefix("MD5=")
