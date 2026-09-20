"""OpenCV 5 DNN subject segmentation — the second opinion that can leave the laptop.

The Red Curtain pipeline borrows two things from Apple Vision (`PersonMatte`, Swift, macOS only):
the seed mask the video matte is propagated from, and the independent silhouette the
`matte_extent` gate compares the matte against. Neither can follow the loop onto AWS compute.
`SubjectSegmenter` is the same job on `cv2.dnn`, so it runs wherever OpenCV runs.

Models (`MODELS` below, both Apache-2.0, plain ONNX for `cv2.dnn.readNet`): PP-HumanSeg as ported
by the OpenCV Zoo — 6 MB, 192×192, two-class softmax; pre/post-processing per the zoo's reference —
and U²-Net's human-segmentation weights (rembg's export) — 176 MB, 320×320, a saliency map. The
person probability is upsampled bilinearly back to the frame as a soft alpha.

Three uses, each measured the archive's way so the opinions are comparable:

    segment(frame)                  a soft alpha (person probability × 255) at the frame's size
    seed(frame, pose_row)           the mask cleaned to the performer, as clean_seed.py does
    matte_extent(matte, mask)       the head-band width ratio the `matte_extent` gate is built on
    edge_separation(comp, mask)     the edge-ring luma ratio the `separation` gate is built on

Resolution is the model's limit, not OpenCV's: 192 px across a 1920 px frame is 10 px per cell.
`crop` runs the network on the pose's own box instead of the whole frame, which is the honest way
to buy resolution without changing the model. `python3 -m stage_ready segcheck` measures both
against the archive's Vision opinions; the README carries the result (planned → live only where
the evidence supports it).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import require_cv2

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = Path(os.environ.get("STAGE_READY_MODELS_DIR", ROOT / "models"))   # the Lambda uses /tmp/models

# The models this seam has been measured with (`python3 -m stage_ready segcheck --model …`). Both
# Apache-2.0, both plain ONNX that cv2.dnn.readNet loads; each entry says how the network wants its
# input and where the person probability comes out.
MODELS = {
    "pphumanseg": {
        "file": "human_segmentation_pphumanseg_2023mar.onnx",
        "sha256": "552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24",
        "source": "https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg",
        "license": "Apache-2.0 (PaddlePaddle authors; OpenCV Zoo port)",
        "input": (192, 192), "mean": (0.5, 0.5, 0.5), "std": (0.5, 0.5, 0.5),
        "read": "softmax_channel_1",           # output 1×2×H×W already softmaxed; channel 1 = person
    },
    "u2net_human_seg": {
        "file": "u2net_human_seg.onnx",
        "sha256": "01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c",
        "source": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx (U²-Net, xuebinqin/U-2-Net)",
        "license": "Apache-2.0",
        "input": (320, 320), "mean": (0.485, 0.456, 0.406), "std": (0.229, 0.224, 0.225),
        "read": "first_output_minmax",         # d0 of the seven side outputs, min-max normalised as rembg does
    },
}
# Measured 2026-09-19 (`segcheck`): U²-Net agrees with the archive's Vision opinion to within 2 % on
# the matte_extent number and 0.95–0.99 IoU on the seed; PP-HumanSeg finds the performer but drops
# hair at 192 px (head widths 4–18 % narrower than Vision's), so it is kept as the fast baseline, not
# the default. The models are not in the repository (6 MB and 176 MB): `fetch()` downloads them
# into models/ and checks the hash.
DEFAULT_MODEL = "u2net_human_seg"
MODEL_SOURCE = MODELS[DEFAULT_MODEL]["source"] + " (Apache-2.0)"
URLS = {
    "pphumanseg": "https://github.com/opencv/opencv_zoo/raw/main/models/human_segmentation_pphumanseg/human_segmentation_pphumanseg_2023mar.onnx",
    "u2net_human_seg": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx",
}


def sha256_of(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str = DEFAULT_MODEL, force: bool = False) -> Path:
    """Download a registered model into models/ and verify its SHA-256. Standard library only."""
    import urllib.request
    spec = MODELS[name]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / spec["file"]
    if path.is_file() and not force and sha256_of(path) == spec["sha256"]:
        return path
    tmp = path.with_suffix(".part")
    urllib.request.urlretrieve(URLS[name], tmp)
    got = sha256_of(tmp)
    if got != spec["sha256"]:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{name}: downloaded file's sha256 {got[:16]}… does not match the registered {spec['sha256'][:16]}…")
    tmp.replace(path)
    return path


class ModelMissing(RuntimeError):
    pass


@dataclass
class SegTiming:
    frames: int = 0
    seconds: float = 0.0

    @property
    def ms_per_frame(self) -> float:
        return 1000.0 * self.seconds / self.frames if self.frames else 0.0


class SubjectSegmenter:
    """OpenCV 5 DNN subject segmentation. CPU, single-threaded by default — deterministic."""

    def __init__(self, model: str | Path | None = None, threads: int = 1):
        cv2 = require_cv2()
        name = str(model or os.environ.get("STAGE_READY_SEG_MODEL", DEFAULT_MODEL))
        self.spec = MODELS.get(name)
        path = MODELS_DIR / self.spec["file"] if self.spec else Path(os.path.expanduser(name))
        if self.spec is None:                          # a path to an ONNX file: treated like pphumanseg
            self.spec = MODELS[DEFAULT_MODEL] | {"file": path.name, "source": str(path)}
        if not path.is_file():
            raise ModelMissing(f"segmentation model not found: {path} — python3 -m stage_ready models fetch {name} "
                               f"(from {self.spec['source']})")
        self.model = path
        self.name = name
        self.INPUT = tuple(self.spec["input"])
        cv2.setNumThreads(threads)
        self.net = cv2.dnn.readNet(str(path))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.timing = SegTiming()

    # ---- the network ------------------------------------------------------------------------
    def _prob(self, bgr) -> Any:
        """Person probability, float32, at the input's size."""
        cv2 = require_cv2()
        import numpy as np
        t0 = time.time()
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        small = cv2.resize(rgb, self.INPUT, interpolation=cv2.INTER_AREA)
        x = (small.astype(np.float32) / 255.0 - np.array(self.spec["mean"], np.float32)) / np.array(self.spec["std"], np.float32)
        self.net.setInput(cv2.dnn.blobFromImage(x))
        if self.spec["read"] == "softmax_channel_1":
            out = self.net.forward()[0]                 # 2 × H × W, already softmaxed (the channels sum to 1)
            p = out[1].astype(np.float32)               # class 1 = person
        else:                                           # U²-Net: d0, the fused side output, min-max normalised
            out = self.net.forward(self.net.getUnconnectedOutLayersNames()[0])[0, 0].astype(np.float32)
            p = (out - out.min()) / max(1e-6, float(out.max() - out.min()))
        p = cv2.resize(p, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
        self.timing.frames += 1; self.timing.seconds += time.time() - t0
        return p

    def segment(self, frame_bgr, crop: tuple[int, int, int, int] | None = None) -> Any:
        """uint8 HxW soft alpha, 0..255. With `crop` (x0, y0, x1, y1) the network sees only that box
        and the alpha is zero outside it — the pose's box, padded, is the natural crop."""
        import numpy as np
        H, W = frame_bgr.shape[:2]
        if crop is None:
            return (self._prob(frame_bgr) * 255).astype(np.uint8)
        x0, y0, x1, y1 = (max(0, int(crop[0])), max(0, int(crop[1])), min(W, int(crop[2])), min(H, int(crop[3])))
        out = np.zeros((H, W), np.uint8)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return out
        out[y0:y1, x0:x1] = (self._prob(frame_bgr[y0:y1, x0:x1]) * 255).astype(np.uint8)
        return out

    # ---- the three uses ---------------------------------------------------------------------
    @staticmethod
    def pose_box(pose_row: dict, W: int, H: int, pad: float = 0.35) -> tuple[int, int, int, int] | None:
        """A box around the pose's joints, padded — wider above the head than below the hips, since
        the crown is what the second opinion is about and the legs run off the frame anyway."""
        xs, ys = [], []
        for k, v in pose_row.items():
            if v in ("", None) or not (k.endswith("_x") or k.endswith("_y")):
                continue
            try:
                (xs if k.endswith("_x") else ys).append(float(v))
            except ValueError:
                pass
        if not xs or not ys:
            return None
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        return (int(min(xs) - pad * w - 0.1 * W), int(min(ys) - 0.6 * h), int(max(xs) + pad * w + 0.1 * W), int(H))

    def seed(self, frame_bgr, pose_row: dict | None = None, thresh: int = 32, crop: bool = True) -> Any:
        """The performer's mask, 0/255, cleaned the way the seed is: the components the pose stands in
        plus the largest. This is what a video matte would be propagated from."""
        import numpy as np
        from .matte import performer_component
        H, W = frame_bgr.shape[:2]
        box = self.pose_box(pose_row, W, H) if (crop and pose_row) else None
        alpha = self.segment(frame_bgr, box)
        comp = performer_component(alpha, pose_row, thresh)
        if comp is None:
            return np.zeros((H, W), np.uint8)
        return (comp.astype(np.uint8) * 255)

    def matte_extent(self, matte_gray, mask) -> float | None:
        """Matte head width / this opinion's head width over the head band — the `matte_extent`
        gate's number for one frame (None when the opinion is too small to compare)."""
        from .matte import head_band_widths
        w = head_band_widths(matte_gray, mask > 127)
        return None if w is None else w[0] / w[1]

    def edge_separation(self, composite_bgr, mask) -> float | None:
        """Inside / outside edge luma ratio on a finished composite, using this opinion's silhouette
        as the edge — the `separation` gate's number for one frame."""
        from .silhouette import edge_luma
        r = edge_luma(composite_bgr, mask)
        if r is None:
            return None
        i, o = r
        return max(i, o) / max(1e-6, min(i, o))
