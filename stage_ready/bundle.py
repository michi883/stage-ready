"""The judge bundle: the media and measurements behind the demo, as files a judge can download.

Performer footage is not in the repository (`demo/clips/*/stills/` is git-ignored — README,
"Real stills and videos"). What a judge gets instead is a private bundle, built here from the Red
Curtain archive, holding exactly what two things need:

    the demo      — the stills and videos the workspace plays   → `demo-media/<clip>/stills/`
    `measure`     — the files INSPECT and VERIFY are computed from, in the archive's own layout,
                    so `--archive <bundle>` works unchanged     → `<source>.mp4`, `work/midtown_<clip>/…`

Whole where a measurement reads every frame (the matte, the warped matte, the completed matte,
the pose track, the solve); sampled where it reads a spread — the 48 source frames `grade_qc`
looks at and the 24 composite frames `separation` looks at, chosen by the same
`vision.sample_indices` the measurements use, so the bundle measures the same number as the
full directory. A MANIFEST.json carries every file's size and SHA-256.

    python3 -m stage_ready bundle --out <dir> [--archive ~/mts] [--dry-run] [clips…]
    python3 -m stage_ready bundle --install <dir>      # in a clone: link the media, name the archive
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .backends.cached import CLIPS, CachedBackend
from .measure import archive_root

WORKDIR_FILES = ("source.key", "matte.key", "params.txt", "params_sep.txt", "track.log", "crown.log",
                 "seed_pick.log", "seed_frame.txt", "seed_mask.png", "separation.log", "pose.csv", "pose_ext.csv", "affine.csv")
WHOLE_DIRS = ("seed", "matte", "matte_ext", "mt")      # every frame is read
BAND_SAMPLES, COMP_SAMPLES = 48, 24                    # grade_qc and separation read a spread


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def plan(archive: Path, clip_ids: list[str] | None = None) -> list[tuple[Path, str]]:
    """(source file, published path) for everything the bundle carries."""
    from .vision import frame_number, sample_indices

    demo = CachedBackend()
    items: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(src: Path, dst: str):
        if dst in seen:
            return
        if not src.exists():
            raise FileNotFoundError(f"bundle: {src} is named by the demo but missing from the archive")
        seen.add(dst)
        items.append((src, dst))

    for clip in demo.clips():
        if clip_ids and clip.id not in clip_ids:
            continue
        a = clip.archive
        if not a.get("workdir"):
            continue
        # -- the demo's media: stills and the videos they link to, as real files
        stills = CLIPS / clip.id / "stills"
        for name in sorted(os.listdir(stills)) if stills.is_dir() else []:
            p = stills / name
            if p.is_file() or p.is_symlink():
                add(p.resolve(), f"demo-media/{clip.id}/stills/{name}")
        # -- the archive: source, deliveries, the workdir
        add(archive / a["source"], a["source"])
        wd = archive / a["workdir"]
        for art in a.get("artifacts", {}).values():
            if art.get("video"):
                add(archive / art["video"], art["video"])
        for f in WORKDIR_FILES:
            if (wd / f).exists():
                add(wd / f, f"{a['workdir']}/{f}")
        for d in WHOLE_DIRS:
            if (wd / d).is_dir():
                for name in sorted(os.listdir(wd / d)):
                    add(wd / d / name, f"{a['workdir']}/{d}/{name}")
        n = len([x for x in os.listdir(wd / "matte") if x.endswith(".png")]) if (wd / "matte").is_dir() else 0
        if (wd / "band").is_dir() and n:
            # the frames grade_qc samples, plus the frames the second opinion is taken on (seed/)
            want = {i + 1 for i in sample_indices(n, BAND_SAMPLES)}
            if (wd / "seed").is_dir():
                want |= {frame_number(x) for x in os.listdir(wd / "seed") if frame_number(x)}
            for name in sorted(os.listdir(wd / "band")):
                if frame_number(name) in want:
                    add(wd / "band" / name, f"{a['workdir']}/band/{name}")
        comps = {art["composite"] for art in a.get("artifacts", {}).values() if art.get("composite")}
        n_mt = len([x for x in os.listdir(wd / "mt") if x.endswith(".png")]) if (wd / "mt").is_dir() else 0
        for c in sorted(comps):
            if (wd / c).is_dir() and n_mt:
                want = {i + 1 for i in sample_indices(n_mt, COMP_SAMPLES)}
                for name in sorted(os.listdir(wd / c)):
                    if frame_number(name) in want:
                        add(wd / c / name, f"{a['workdir']}/{c}/{name}")
    return items


README = """Stage Ready — judge bundle
==========================

The performer footage and the measured intermediates behind the demo. The repository itself holds
no footage (the performers agreed to judges seeing it, not to a public repository).

Two things this gives you:

1. The demo's media. From a clone of the repository:

       python3 -m stage_ready bundle --install <this directory>

   links demo-media/<clip>/stills into demo/clips/<clip>/stills, and the workspace
   (`python3 -m stage_ready serve`, then http://127.0.0.1:8765/?demo=1) plays the videos.

2. The files INSPECT and VERIFY are computed from, in the Red Curtain archive's own layout:

       export STAGE_READY_ARCHIVE=<this directory>
       .venv/bin/python -m stage_ready measure          # every fixture number, recomputed with OpenCV 5
       .venv/bin/python -m stage_ready run ethel --live

   Whole where a measurement reads every frame (matte/, matte_ext/, mt/, seed/, pose*.csv,
   affine.csv); sampled where it reads a spread (band/: the 48 frames grade_qc reads; comp*/:
   the 24 frames separation reads — chosen by the same rule, so the numbers are the same).

MANIFEST.json lists every file with its size and SHA-256.
"""


def build(out: Path, archive: Path, clip_ids: list[str] | None = None, dry_run: bool = False) -> dict[str, Any]:
    items = plan(archive, clip_ids)
    total = sum(src.stat().st_size for src, _ in items)
    if dry_run:
        return {"files": len(items), "bytes": total, "items": [dst for _, dst in items]}
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}
    for src, dst in items:
        p = out / dst
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, p)
        manifest[dst] = {"bytes": p.stat().st_size, "sha256": _sha256(p)}
    (out / "README.txt").write_text(README)
    (out / "MANIFEST.json").write_text(json.dumps({"archive": str(archive), "files": manifest}, indent=1))
    return {"files": len(items), "bytes": total, "out": str(out)}


def install(bundle: Path) -> list[str]:
    """In a clone: point demo/clips/<clip>/stills at the bundle's media. Returns what it did."""
    done = []
    media = bundle / "demo-media"
    if not media.is_dir():
        raise FileNotFoundError(f"bundle: {media} not found — is {bundle} a Stage Ready bundle?")
    for clip_dir in sorted(media.iterdir()):
        stills = CLIPS / clip_dir.name / "stills"
        stills.mkdir(parents=True, exist_ok=True)
        for f in sorted((clip_dir / "stills").iterdir()):
            dst = stills / f.name
            if dst.is_symlink() or dst.exists():
                dst.unlink()
            os.symlink(f.resolve(), dst)
            done.append(f"{dst.relative_to(CLIPS.parent.parent)} -> {f.resolve()}")
    return done


def verify(bundle: Path) -> list[str]:
    """Every manifest entry present with the right hash. Returns the problems."""
    m = json.loads((bundle / "MANIFEST.json").read_text())["files"]
    problems = []
    for rel, info in m.items():
        p = bundle / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif _sha256(p) != info["sha256"]:
            problems.append(f"hash differs: {rel}")
    return problems
