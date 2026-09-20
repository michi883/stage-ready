"""Does the OpenCV 5 DNN opinion agree with the archive's Apple Vision opinion? Measured, per clip.

Three comparisons, on the frames the archive itself used, so nothing is cherry-picked:

    seed          on the archive's seed frame: the DNN seed (cleaned to the performer) against the
                  Vision seed the matte was propagated from — IoU, and the head-band width ratio
    second opinion on the archive's Vision frames (`seed/`, the 16–17 frames matte_qc compared): the
                  `matte_extent` number with the DNN as the opinion, beside the archived number with
                  Vision as the opinion — and the two opinions' head widths against each other
    separation    on the 24 composite frames `separation` samples: the edge-ring luma ratio using
                  the DNN silhouette of the finished composite as the edge, beside the archived
                  number that uses the pipeline's own warped matte

`python3 -m stage_ready segcheck [clips] [--no-crop]` prints the table; `--json` dumps it. The
README's "planned → live" claim for the DNN is made from this output, not from the model card.
"""
from __future__ import annotations

import glob
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from ..backends.cached import CachedBackend
from ..measure import ArchiveMeasurer
from ..profile import Profile
from . import require_cv2, read_pose, sample_indices
from .matte import head_band_widths, performer_component
from .segment import SubjectSegmenter, MODEL_SOURCE


def _iou(a, b) -> float:
    inter, union = (a & b).sum(), (a | b).sum()
    return float(inter) / float(union) if union else 0.0


def check_clip(clip, m: ArchiveMeasurer, seg: SubjectSegmenter, crop: bool = True) -> dict[str, Any]:
    cv2 = require_cv2()
    import numpy as np

    wd = m.workdir(clip)
    pose = read_pose(str(wd / "pose.csv"))
    out: dict[str, Any] = {"clip": clip.id, "workdir": str(wd.relative_to(m.root)), "crop": crop}

    # ---- 1. seed
    n = int((wd / "seed_frame.txt").read_text().strip())
    frame = cv2.imread(str(wd / "band" / f"f_{n:04d}.jpg"))
    vis_seed = cv2.imread(str(wd / "seed_mask.png"), cv2.IMREAD_GRAYSCALE) > 128
    t0 = time.time()
    dnn_seed = seg.seed(frame, pose[n - 1], crop=crop) > 127
    t_seed = time.time() - t0
    wv = head_band_widths(vis_seed.astype(np.uint8) * 255, vis_seed)   # vision head width, against itself
    wd_ = head_band_widths(dnn_seed.astype(np.uint8) * 255, dnn_seed)
    out["seed"] = {"frame": n, "iou": round(_iou(dnn_seed, vis_seed), 3), "dnn_px": int(dnn_seed.sum()), "vision_px": int(vis_seed.sum()),
                   "head_width_dnn": wd_[1] if wd_ else None, "head_width_vision": wv[1] if wv else None, "seconds": round(t_seed, 3)}

    # ---- 2. second opinion, on the archive's Vision frames
    rows = []
    mattes = sorted(glob.glob(str(wd / "matte" / "f_*.png")))
    for v in sorted(glob.glob(str(wd / "seed" / "f_*.png"))):
        k = int(re.search(r"f_(\d+)", os.path.basename(v)).group(1))
        if k > len(mattes):
            continue
        matte = cv2.imread(mattes[k - 1], cv2.IMREAD_GRAYSCALE)
        vis = cv2.imread(v, cv2.IMREAD_GRAYSCALE)
        fr = cv2.imread(str(wd / "band" / f"f_{k:04d}.jpg"))
        if matte is None or vis is None or fr is None or vis.shape != matte.shape:
            continue
        row = pose[k - 1] if k - 1 < len(pose) else None
        vis_c = performer_component(vis, row, 32)
        dnn_c = seg.seed(fr, row, crop=crop) > 127
        if vis_c is None or not vis_c.any() or not dnn_c.any():
            continue
        a = head_band_widths(matte, vis_c); b = head_band_widths(matte, dnn_c)
        if a is None or b is None:
            continue
        rows.append({"frame": k, "matte_px": a[0], "vision_px": a[1], "dnn_px": b[1],
                     "ratio_vision": round(a[0] / a[1], 3), "ratio_dnn": round(b[0] / b[1], 3), "dnn_over_vision": round(b[1] / a[1], 3),
                     "iou": round(_iou(dnn_c, vis_c), 3)})
    if rows:
        rv = float(np.median([r["ratio_vision"] for r in rows])); rd = float(np.median([r["ratio_dnn"] for r in rows]))
        out["second_opinion"] = {"frames": len(rows), "matte_extent_vision": round(rv, 3), "matte_extent_dnn": round(rd, 3),
                                 "dnn_over_vision_head_width_median": round(float(np.median([r["dnn_over_vision"] for r in rows])), 3),
                                 "iou_median": round(float(np.median([r["iou"] for r in rows])), 3),
                                 "gate_pass_vision": rv >= 0.9, "gate_pass_dnn": rd >= 0.9, "rows": rows}

    # ---- 3. separation on the composites, DNN silhouette as the edge
    seps = {}
    for art, spec in clip.archive.get("artifacts", {}).items():
        comp = wd / spec.get("composite", "") if spec.get("composite") else None
        if not comp or not comp.is_dir():
            continue
        mt = sorted(glob.glob(str(wd / "mt" / "*.png")))
        comps = {int(re.search(r"c_(\d+)", os.path.basename(f)).group(1)): f for f in glob.glob(str(comp / "*.png"))}
        ins, outs, ins_m, outs_m, used = [], [], [], [], 0
        for i in sample_indices(len(mt), 24):
            f = comps.get(i + 1)
            if f is None:
                continue
            c = cv2.imread(f); a = cv2.imread(mt[i], cv2.IMREAD_GRAYSCALE)
            mask = seg.segment(c)                        # the finished composite: performer on the curtain
            from .silhouette import edge_luma
            r = edge_luma(c, mask); r2 = edge_luma(c, a)
            if r is None or r2 is None:
                continue
            ins.append(r[0]); outs.append(r[1]); ins_m.append(r2[0]); outs_m.append(r2[1]); used += 1
        if used:
            i_, o_ = float(np.mean(ins)), float(np.mean(outs)); im_, om_ = float(np.mean(ins_m)), float(np.mean(outs_m))
            seps[art] = {"frames": used, "dnn": {"inside": round(i_, 3), "outside": round(o_, 3), "ratio": round(max(i_, o_) / max(1e-6, min(i_, o_)), 2)},
                         "matte": {"inside": round(im_, 3), "outside": round(om_, 3), "ratio": round(max(im_, om_) / max(1e-6, min(im_, om_)), 2)}}
    out["separation"] = seps
    return out


def run(clip_ids: list[str] | None, archive: str | None, crop: bool = True, as_json: bool = False, model: str | None = None) -> dict[str, Any]:
    cv2 = require_cv2()
    demo = CachedBackend(); m = ArchiveMeasurer(archive); Profile.load()
    seg = SubjectSegmenter(model)
    report: dict[str, Any] = {"opencv": cv2.__version__, "model": str(seg.model.name), "model_source": seg.spec["source"], "license": seg.spec["license"], "crop": crop, "clips": {}}
    for clip in demo.clips():
        if clip_ids and clip.id not in clip_ids:
            continue
        try:
            m.workdir(clip)
        except Exception as e:  # noqa: BLE001
            report["clips"][clip.id] = {"skipped": str(e)}; continue
        r = check_clip(clip, m, seg, crop)
        report["clips"][clip.id] = r
        if not as_json:
            s = r["seed"]; so = r.get("second_opinion", {})
            print(f"== {clip.name} ({clip.id})")
            print(f"   seed frame {s['frame']}: IoU {s['iou']} vs Vision; head width dnn {s['head_width_dnn']} px / vision {s['head_width_vision']} px")
            if so:
                print(f"   second opinion over {so['frames']} frames: matte_extent with Vision {so['matte_extent_vision']} ({'pass' if so['gate_pass_vision'] else 'FAIL'}), "
                      f"with DNN {so['matte_extent_dnn']} ({'pass' if so['gate_pass_dnn'] else 'FAIL'}); DNN/Vision head width {so['dnn_over_vision_head_width_median']}, IoU {so['iou_median']}")
                worst = min(so["rows"], key=lambda x: x["ratio_dnn"])
                print(f"      worst DNN frame {worst['frame']}: matte {worst['matte_px']} px, vision {worst['vision_px']} px, dnn {worst['dnn_px']} px")
            for art, v in r["separation"].items():
                print(f"   separation {art}: matte-edge {v['matte']['ratio']}× ({v['matte']['inside']}/{v['matte']['outside']})  DNN-edge {v['dnn']['ratio']}× ({v['dnn']['inside']}/{v['dnn']['outside']})  over {v['frames']} frames")
    report["timing"] = {"inferences": seg.timing.frames, "ms_per_frame": round(seg.timing.ms_per_frame, 1)}
    if not as_json:
        print(f"OpenCV {cv2.__version__} · {seg.model.name} · {seg.timing.frames} inferences at {seg.timing.ms_per_frame:.1f} ms/frame (CPU, 1 thread, crop={crop})")
    else:
        print(json.dumps(report, indent=1))
    return report
