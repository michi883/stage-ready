"""CLI.

    python -m stage_ready serve [--port 8765]        serve the UI and the API
    python -m stage_ready run  [sandy ethel zach] [--live]   print a run's trace as text
    python -m stage_ready trace [sandy ethel zach]           print a run's events as JSON lines
    python -m stage_ready measure [sandy ethel zach] [--archive ~/mts] [--json]
                                    compute INSPECT and VERIFY with OpenCV 5 over the archived
                                    workdirs and print every number next to its demo fixture
    python -m stage_ready bundle --out <dir> [--archive ~/mts] [--dry-run] [clips…]
                                    build the judge bundle: the demo's media and the files
                                    `measure` reads, in the archive's layout, with a manifest
    python -m stage_ready bundle --install <dir> | --verify <dir>
                                    in a clone: link a bundle's media into demo/clips; check one
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .backends import get_backend
from .loop import run
from .profile import Profile


def _text(ev: dict) -> str:
    t = ev["type"]
    if t == "run.start":
        return f"== {ev['clip']['name']} — {ev['clip']['brief']}  [{ev['backend']}, profile {ev['profile']['name']}]"
    if t == "phase":
        extra = {k: v for k, v in ev.items() if k not in ("type", "clip", "phase")}
        return f"  ▶ {ev['phase'].upper()} {extra if extra else ''}"
    if t == "inspect.result":
        r = ev["result"]
        lines = [f"    inspect {r['target']}: {len(r['findings'])} findings" + (" (cached)" if r["cached"] else "")]
        for f in r["findings"]:
            mark = {"pass": "✓", "fail": "✗", "warn": "!", "info": "·"}[f["status"]]
            lines.append(f"      {mark} {f['id']:<18} {f['detail']}")
        return "\n".join(lines)
    if t == "decide.result":
        d = ev["decision"]
        return f"    decide #{ev['ordinal']}: {d['action']}" + (f" {d['strategy']}" if d.get("strategy") else "") + \
               f"  (cites {', '.join(d['cites'])})\n      “{d['reasoning']}”"
    if t == "guard":
        return f"    GUARD: {ev['reason']}"
    if t == "fix.result":
        r = ev["result"]
        return f"    fix {r['strategy']} → {r['artifact']}: " + "; ".join(s["summary"] for s in r["stages"])
    if t == "fix.rejected":
        return f"    FIX REJECTED {ev['strategy']}: new defects {ev['new_defects']}"
    if t == "process.result":
        r = ev["result"]
        lines = [f"    process {r['strategy']} → {r['artifact']} (attempt {ev['attempt']})"]
        for s in r["stages"]:
            tag = "reused" if s["reused"] else ("cached" if s["cached"] else f"{s['duration_ms']/1000:.0f}s")
            lines.append(f"      {s['id']:<10} [{tag:>6}] {s['summary']}")
        return "\n".join(lines)
    if t == "verify.result":
        r = ev["result"]
        lines = [f"    verify {r['artifact']}: {'PASS' if ev['passed'] else 'FAIL'}  budget {ev['budget']}"]
        for g in r["gates"]:
            mark = {"pass": "✓", "fail": "✗", "warn": "!", "info": "·"}[g["status"]]
            lines.append(f"      {mark} {g['id']:<14} {g['value']!s:<8} {g['detail']}")
        return "\n".join(lines)
    if t == "run.end":
        if ev["outcome"] == "delivered":
            d = ev["delivery"]
            return f"  ■ DELIVERED {d['artifact']} via {d['strategy']} after {d['attempts']} attempt(s), fixes {d['fixes']}\n    path: {' → '.join(ev['path'])}\n    {d['measurements']}"
        r = ev["reshoot"]
        return f"  ■ RESHOOT REQUEST\n    path: {' → '.join(ev['path'])}\n" + \
               "\n".join(f"    - {i['label']}: {i['value']} vs {i['threshold']} — {i['guidance']}" for i in r["items"])
    return f"    {t}: {json.dumps(ev)[:200]}"


def _measure(ids: list[str], archive: str | None, as_json: bool) -> int:
    """The accept test for the OpenCV 5 port (PLAN.md step 2a): the live measurer's numbers
    beside the fixture's, for every finding and gate, with the disagreements marked."""
    from .backends.cached import CachedBackend, FixtureMissing
    from .measure import ArchiveMeasurer, ArchiveMissing
    from .models import to_dict
    from .vision import require_cv2

    cv2 = require_cv2()
    demo = CachedBackend()
    m = ArchiveMeasurer(archive)
    profile = Profile.load()
    ids = ids or [c.id for c in demo.clips()]
    report: dict[str, Any] = {"opencv": cv2.__version__, "archive": str(m.root), "clips": {}}
    disagreements = 0

    def num(v):
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def compare(kind, fixture_items, live_items):
        nonlocal disagreements
        fx = {f["id"]: f for f in fixture_items}
        for f in live_items:
            g = fx.get(f["id"])
            if g is None:
                print(f"      {f['id']:<16} {f['status']:<5} {f['value']!s:<28} (no fixture entry)")
                continue
            a, b = g["value"], f["value"]
            same_status = g["status"] == f["status"]
            if isinstance(a, dict) and isinstance(b, dict):
                keys = [k for k in a if num(a[k]) is not None and num(b.get(k)) is not None]
                close = all(abs(a[k] - b[k]) <= max(0.02 * abs(a[k]), 0.006) for k in keys) if keys else (a == b)
            elif num(a) is not None and num(b) is not None:
                close = abs(a - b) <= max(0.02 * abs(a), 0.006)
            else:
                close = a == b
            mark = "=" if (close and same_status) else ("~" if same_status else "!")
            if mark != "=":
                disagreements += 1
            print(f"      {mark} {f['id']:<16} fixture {g['status']:<5} {a!s:<26} live {f['status']:<5} {b!s}")
            rows.append({"kind": kind, "id": f["id"], "fixture": a, "live": b, "fixture_status": g["status"],
                         "live_status": f["status"], "agree": mark == "="})

    for cid in ids:
        clip = demo.clip(cid)
        print(f"== {clip.name} ({cid}) — {clip.fixture}")
        rows: list[dict[str, Any]] = []
        try:
            wd = m.workdir(clip)
        except ArchiveMissing as e:
            print(f"   skipped: {e}"); report["clips"][cid] = {"skipped": str(e)}; continue
        print(f"   archive: {wd.relative_to(m.root)}  source: {clip.archive['source']}")
        targets = ["source"] + (["fixed"] if (demo.CLIPS_DIR / cid / "inspect.fixed.json").exists() else [])
        out: dict[str, Any] = {"inspect": {}, "verify": {}}
        for target in targets:
            live = to_dict(m.inspect(clip, target, profile))
            out["inspect"][target] = live
            print(f"   inspect {target}  ({live['duration_ms'] / 1000:.1f}s live)")
            try:
                fixture = demo.inspect(clip, target, profile, None)
                compare("inspect." + target, to_dict(fixture)["findings"], live["findings"])
            except FixtureMissing:
                for f in live["findings"]:
                    print(f"      {f['id']:<16} {f['status']:<5} {f['value']!s}")
        for art, spec in clip.archive.get("artifacts", {}).items():
            try:
                live = to_dict(m.verify(clip, art, profile))
            except ArchiveMissing as e:
                print(f"   verify {art}: skipped — {e}"); continue
            out["verify"][art] = live
            print(f"   verify {art}  ({live['duration_ms'] / 1000:.1f}s live; {spec.get('composite') or spec.get('video')})")
            if spec.get("note"):
                print(f"      note: {spec['note']}")
            try:
                fixture = demo.verify(clip, art, profile, None)
                compare("verify." + art, to_dict(fixture)["gates"], live["gates"])
            except FixtureMissing:
                for g in live["gates"]:
                    print(f"      {g['id']:<16} {g['status']:<5} {g['value']!s}")
            print(f"      measurements: {live['measurements']}")
        out["comparison"] = rows
        report["clips"][cid] = out
        print()
    print(f"OpenCV {cv2.__version__}; {disagreements} disagreement(s) marked ! (status differs) or ~ (value differs by more than 2 %).")
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def _bundle(a) -> int:
    from pathlib import Path
    from . import bundle as B
    from .measure import archive_root

    if a.install:
        for line in B.install(Path(a.install).expanduser().resolve()):
            print("  " + line)
        print(f"media linked. For live measurement: export STAGE_READY_ARCHIVE={Path(a.install).expanduser().resolve()}")
        return 0
    if a.verify:
        problems = B.verify(Path(a.verify).expanduser().resolve())
        print("\n".join(problems) if problems else "bundle complete: every manifest entry present with its hash")
        return 1 if problems else 0
    if not a.out:
        print("bundle: --out <dir> (or --install / --verify)"); return 2
    r = B.build(Path(a.out).expanduser().resolve(), archive_root(a.archive), a.clips or None, dry_run=a.dry_run)
    if a.dry_run:
        by_top: dict[str, int] = {}
        for it in r["items"]:
            by_top[it.split("/")[0] if "/" in it else "(root)"] = by_top.get(it.split("/")[0] if "/" in it else "(root)", 0) + 1
        for k, v in sorted(by_top.items()):
            print(f"  {v:6d}  {k}/")
        print(f"{r['files']} files, {r['bytes'] / 1e9:.2f} GB (dry run)")
    else:
        print(f"{r['files']} files, {r['bytes'] / 1e9:.2f} GB -> {r['out']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stage_ready")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=8765); s.add_argument("--host", default="127.0.0.1")
    r = sub.add_parser("run"); r.add_argument("clips", nargs="*"); r.add_argument("--live", action="store_true")
    t = sub.add_parser("trace"); t.add_argument("clips", nargs="*"); t.add_argument("--live", action="store_true")
    m = sub.add_parser("measure"); m.add_argument("clips", nargs="*"); m.add_argument("--archive", default=None); m.add_argument("--json", action="store_true")
    b = sub.add_parser("bundle"); b.add_argument("clips", nargs="*"); b.add_argument("--out", default=None); b.add_argument("--archive", default=None)
    b.add_argument("--dry-run", action="store_true"); b.add_argument("--install", default=None); b.add_argument("--verify", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "measure":
        return _measure(a.clips, a.archive, a.json)
    if a.cmd == "bundle":
        return _bundle(a)

    if a.cmd == "serve":
        from .server import serve
        return serve(a.host, a.port)

    backend = get_backend(demo=not a.live)
    profile = Profile.load()
    ids = a.clips or [c.id for c in backend.clips()]
    rc = 0
    for cid in ids:
        clip = backend.clip(cid)
        try:
            for ev in run(clip, profile, backend):
                print(json.dumps(ev, ensure_ascii=False) if a.cmd == "trace" else _text(ev))
        except NotImplementedError as e:            # a live step that is not wired yet stops the run, loudly
            ev = {"type": "error", "clip": cid, "message": str(e)}
            print(json.dumps(ev, ensure_ascii=False) if a.cmd == "trace" else f"  ✗ STOPPED — {e}")
            rc = 2
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
