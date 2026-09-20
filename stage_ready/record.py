"""Write a clip's cached fixtures from measurement, not by hand.

The demo replays `demo/clips/<id>/*.json`. For the measured records — INSPECT and VERIFY — this
runs `ArchiveMeasurer` over the clip's archived workdir and writes what it measured, with the
provenance line saying so. For the process record it reads what the Red Curtain run left behind
(seed_pick.log, matte.key, track.log, crown.log, params.txt) and takes each stage's duration from
the workdir's file modification times: the pipeline writes each stage's output when it finishes,
so the files are a timeline, to the second — for a single uninterrupted run. A workdir re-run in
pieces (the archive's Ethel, whose seed and solve were redone on different days) has no usable
timeline, and its curated process record stays.

What is not written here: the agent's decisions (`decide.<n>.json`). Those are the cached agent's
words about the findings in front of it; they cite finding ids that `CachedBackend.decide` checks
against the recorded findings.

    python3 -m stage_ready record <clip> [--archive DIR] [--fixed] [--out DIR]
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .backends.cached import CLIPS, CachedBackend
from .measure import ArchiveMeasurer
from .models import to_dict
from .profile import Profile


def _dump(path: Path, d: dict[str, Any]) -> None:
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")


def _clean(rec: dict[str, Any]) -> dict[str, Any]:
    """The fixture is the record's fields; the derived properties (`failing`, `passed`) are not stored."""
    return {k: v for k, v in rec.items() if k not in ("failing", "passed", "cached")}


def _mtime(p: Path) -> float:
    if p.is_dir():
        files = [p / f for f in os.listdir(p)]
        return max((f.stat().st_mtime for f in files), default=p.stat().st_mtime)
    return p.stat().st_mtime if p.exists() else 0.0


def _first_mtime(p: Path) -> float:
    if p.is_dir():
        files = [p / f for f in os.listdir(p)]
        return min((f.stat().st_mtime for f in files), default=p.stat().st_mtime)
    return p.stat().st_mtime if p.exists() else 0.0


def process_record(wd: Path, root: Path, video: str | None, profile: Profile, artifact: str = "attempt_1", n_frames: int | None = None) -> dict[str, Any]:
    """`process.standard.json` from the workdir's logs and timeline. `n_frames` stands in for the
    matte count when the workdir holds only the logs (the S3 cache path)."""
    text = lambda f: (wd / f).read_text() if (wd / f).exists() else ""
    seed_log, track_log, crown_log, params = text("seed_pick.log"), text("track.log"), text("crown.log"), text("params.txt").strip()
    n = len([f for f in os.listdir(wd / "matte") if f.endswith(".png")]) if (wd / "matte").is_dir() else (n_frames or 0)
    seed_frame = text("seed_frame.txt").strip()
    m = re.search(r"pick_seed: frame (\d+) of (\d+) candidates \(head (\d+) px, coverage ([\d.]+)%, ([^,]+), edges touched (\d+), threshold >(\d+)\)", seed_log)
    seed_summary = (f"Vision on {m.group(2)} candidate frames; seed from frame {m.group(1)} ({m.group(5)}, head {m.group(3)} px, coverage {m.group(4)} %)."
                    if m else f"Seed from frame {seed_frame}.")
    ht = re.search(r"head_target=([\d.]+)", track_log); sc = re.search(r"scale ([\d.]+)\.\.([\d.]+) \(median ([\d.]+)\)", track_log)
    hs = re.search(r"head height spread ([\d.]+)% of source -> ([\d.]+)% of output", track_log)
    cut = re.search(r"cut off at frame bottom on (\d+)%", track_log)
    cap = re.search(r"performer reaches (\d+)% of canvas width at HEAD_TARGET ([\d.]+) \(cap (\d+)%\)", track_log)
    track_summary = (f"head_target {ht.group(1) if ht else '?'}" + (" (pushed from the floor by the size cap)" if cap else " — the floor, unchanged")
                     + (f"; scale {sc.group(1)}..{sc.group(2)} (median {sc.group(3)})" if sc else "")
                     + (f"; head height spread {hs.group(1)} % of source → {hs.group(2)} % of output" if hs else "")
                     + (f"; cut off at the frame bottom on {cut.group(1)} % of frames." if cut else "."))
    cr = re.search(r"crown cut on (\d+) frames \((\d+)% of the clip\); (\d+) completed from (\d+) reference frames", crown_log)
    ext = re.search(r"ext_top=(\d+)", crown_log)
    if cr:
        crown_summary = f"Crown cut on {cr.group(1)} frames ({cr.group(2)} %) — {cr.group(3)} completed from {cr.group(4)} of the performer's own uncut frames; picture extended by {ext.group(1) if ext else '?'} rows. Their pixels, a different moment; nothing painted."
    elif "crown cut on 0 frames" in crown_log or crown_log:
        crown_summary = "The crown is inside the picture on every frame — nothing to complete."
    else:
        crown_summary = "Not run."
    grade = {k: float(v) for k, v in re.findall(r"(keydx|rimdx|fgexp)=(-?[\d.]+)", params)}
    look = {k: float(v) for k, v in re.findall(r"(rimamt|lwamt|shadr)=(-?[\d.]+)", params)}
    lift = round(look.get("shadr", 0.018) - 0.018, 3)
    fps = re.search(r"([\d.]+) fps", text("track.log")) or None
    prof = profile.data
    canvas = [int(prof["canvas"]["w"]), int(prof["canvas"]["h"])]

    # the timeline: each stage's output is written when the stage ends
    t_band0, t_band = _first_mtime(wd / "band"), _mtime(wd / "band")
    t_pose = _mtime(wd / "pose.csv"); t_seed = _mtime(wd / "seed_mask.png")
    t_matte = _mtime(wd / "matte.key") or _mtime(wd / "matte"); t_crown = _mtime(wd / "crown.log") or t_matte
    t_track = _mtime(wd / "affine.csv"); t_warp = max(_mtime(wd / "fg"), _mtime(wd / "mt")); t_grade = _mtime(wd / "params.txt")
    t_comp = _mtime(wd / "comp"); t_enc = _mtime(root / video) if video and (root / video).exists() else t_comp
    dur = lambda a, b: max(0, int(round((b - a) * 1000)))
    stages = [
        {"id": "seed", "label": "Seed mask", "tool": "PersonMatte + pick_seed.py + clean_seed.py", "duration_ms": dur(t_pose, t_seed), "summary": seed_summary},
        {"id": "matte", "label": "Video matte", "tool": "MatAnyone 2 (local MPS)", "duration_ms": dur(t_seed, t_matte), "cached": True,
         "summary": f"{n} mattes propagated both ways from frame {seed_frame} — keyed on source SHA-256 + seed SHA-256 (matte.key); a repeat run is a cache hit."},
        {"id": "crown", "label": "Crown completion", "tool": "complete_crown.py", "duration_ms": dur(t_matte, t_crown), "summary": crown_summary},
        {"id": "track", "label": "Tracked reframe solve", "tool": "track_frame.py", "duration_ms": dur(t_crown, t_track), "summary": track_summary,
         "params": {"head_target": float(ht.group(1)) if ht else None, "scale_min": float(sc.group(1)) if sc else None,
                    "scale_max": float(sc.group(2)) if sc else None, "scale_median": float(sc.group(3)) if sc else None}},
        {"id": "warp", "label": "Reframe to canvas", "tool": "warp.py", "duration_ms": dur(t_track, t_warp), "summary": f"{canvas[0]}×{canvas[1]}, one resample."},
        {"id": "grade", "label": "Measured grade", "tool": "auto_grade.py", "duration_ms": dur(t_warp, t_grade),
         "summary": " ".join(f"{k}={v:g}" for k, v in grade.items()) + " — measured off the recording, not typed.", "params": grade},
        {"id": "composite", "label": "Composite", "tool": "Composite", "duration_ms": dur(t_grade, t_comp),
         "summary": f"{n} frames on the Red Curtain plate — light wrap {look.get('lwamt', 0.5):g}, rim {look.get('rimamt', 0.28):g}."},
        {"id": "encode", "label": "Encode", "tool": "ffmpeg", "duration_ms": dur(t_comp, t_enc), "summary": "H.264 CRF 20, faststart, source audio copied."},
    ]
    return {
        "provenance": f"recorded from the archived run: {wd.relative_to(root)} — seed_pick.log, matte.key, track.log, crown.log, params.txt; stage durations from the workdir's file times (python3 -m stage_ready record)",
        "artifact": artifact, "duration_ms": sum(s["duration_ms"] for s in stages), "stages": stages,
        "params": {"look": prof["look"]["id"], **grade, "rimamt": look.get("rimamt", 0.28), "lwamt": look.get("lwamt", 0.5), "shadow_lift": lift},
        "output": {"canvas": canvas, "frames": n, "head_target": float(ht.group(1)) if ht else None, "scale_median": float(sc.group(3)) if sc else None},
    }


def record(clip_id: str, archive: str | None = None, fixed: bool = False, out: Path | None = None) -> list[Path]:
    demo = CachedBackend()
    clip = demo.clip(clip_id)
    profile = Profile.load()
    m = ArchiveMeasurer(archive)
    wd = m.workdir(clip)
    out = out or (CLIPS / clip_id)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for target in ["source"] + (["fixed"] if fixed else []):
        rec = _clean(to_dict(m.inspect(clip, target, profile)))
        rec["provenance"] = f"measured: OpenCV 5 over {wd.relative_to(m.root)} — python3 -m stage_ready record {clip_id} (stage_ready.measure; every value computed from the archived files)"
        p = out / f"inspect.{target}.json"; _dump(p, rec); written.append(p)
    for art, spec in clip.archive.get("artifacts", {}).items():
        rec = _clean(to_dict(m.verify(clip, art, profile)))
        rec["provenance"] = f"measured: OpenCV 5 over {wd.relative_to(m.root)}, {spec.get('composite') or spec.get('video')} — python3 -m stage_ready record {clip_id}"
        p = out / f"verify.{art}.json"; _dump(p, rec); written.append(p)
    first = next(iter(clip.archive.get("artifacts", {}).values()), {})
    p = out / "process.standard.json"; _dump(p, process_record(wd, m.root, first.get("video"), profile)); written.append(p)
    return written
