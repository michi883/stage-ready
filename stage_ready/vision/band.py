"""The picture area of a clip — where the recorded picture is inside the file.

Phone exports are routinely padded with hard black bars, and the performer is then cropped by
the bottom of the *picture*, not the bottom of the frame. Getting this wrong is what leaves a
torso floating over the stage, so it is measured rather than assumed. `sandy_hackett_v2.mp4`
is a 3:2 picture pillarboxed inside 16:9: 1620×1080 at +150+0.

Port of the archive's `tools/detect_band.py`: every `step`-th frame is reduced to its row and
column mean levels, the maximum over the sampled frames is taken (a bar is black on every frame;
picture is not), and the picture is the span of rows and columns whose level ever rose above the
threshold. Dimensions are kept even for H.264.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import require_cv2


@dataclass
class Band:
    w: int
    h: int
    x: int
    y: int
    file_w: int                   # the container's frame size
    file_h: int
    frames_read: int
    frames_sampled: int

    @property
    def fills_file(self) -> bool:
        return (self.w, self.h, self.x, self.y) == (self.file_w, self.file_h, 0, 0)

    def __str__(self) -> str:
        return f"{self.w}x{self.h}+{self.x}+{self.y}"


def detect_band(path: str, step: int = 30, thresh: float = 8.0) -> Band:
    cv2 = require_cv2()
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    rows = cols = None
    i = sampled = 0
    file_w = file_h = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        if i == 0:
            file_h, file_w = im.shape[:2]
        if i % step == 0:
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
            r, c = g.mean(axis=1), g.mean(axis=0)
            rows = r if rows is None else np.maximum(rows, r)
            cols = c if cols is None else np.maximum(cols, c)
            sampled += 1
        i += 1
    cap.release()
    if rows is None:
        raise ValueError(f"detect_band: no frames in {path}")

    ry = np.where(rows > thresh)[0]
    rx = np.where(cols > thresh)[0]
    y0, y1 = int(ry.min()), int(ry.max())
    x0, x1 = int(rx.min()), int(rx.max())
    w, h = (x1 - x0 + 1) & ~1, (y1 - y0 + 1) & ~1
    return Band(w=w, h=h, x=x0, y=y0, file_w=file_w, file_h=file_h, frames_read=i, frames_sampled=sampled)
