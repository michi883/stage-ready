"""CLI.

    python -m stage_ready serve [--port 8765]        serve the UI and the API
    python -m stage_ready run  [sandy ethel zach] [--live]   print a run's trace as text (--live: the AWS hybrid)
    python -m stage_ready aws status | sync <clip…> | deploy [--layer DIR]
                                    identity (STS) and bucket status; upload a clip's workdir, source and
                                    deliveries under sources/work/artifacts/<sha256>/; publish the OpenCV 5
                                    layer and the measurement Lambda. Default credential chain only.
    python -m stage_ready aws web-deploy | web-publish | web-invalidate
                                    the public endpoint: CloudFront + private S3 (UI, media) + the API
                                    Lambda; web-publish re-uploads the static files and invalidates
    python -m stage_ready trace [sandy ethel zach]           print a run's events as JSON lines
    python -m stage_ready measure [sandy ethel zach] [--archive ~/mts] [--json] [--opinion dnn]
                                    compute INSPECT and VERIFY with OpenCV 5 over the archived
                                    workdirs and print every number next to its demo fixture;
                                    --opinion dnn uses the DNN segmenter as matte_extent's second opinion
    python -m stage_ready bundle --out <dir> [--archive ~/mts] [--dry-run] [clips…]
                                    build the judge bundle: the demo's media and the files
                                    `measure` reads, in the archive's layout, with a manifest
    python -m stage_ready bundle --install <dir> | --verify <dir>
                                    in a clone: link a bundle's media into demo/clips; check one
    python -m stage_ready segcheck [clips] [--archive ~/mts] [--no-crop] [--json] [--model pphumanseg|u2net_human_seg]
                                    the OpenCV 5 DNN SubjectSegmenter against the archive's Apple
                                    Vision opinions: seed, matte-extent second opinion, separation
    python -m stage_ready agent-eval [--model ID] [--repeat N] [--clips …] [--json]
                                    replay the current fixture DECIDE states through a Bedrock model and
                                    score action, strategy, citations, schema, latency and tokens
    python -m stage_ready models [list | fetch <name>]
                                    the DNN segmentation models: registered names, sources, hashes;
                                    fetch downloads one into models/ and verifies its SHA-256
    python -m stage_ready record <clip> [--archive ~/mts] [--fixed] [--out DIR]
                                    write the clip's inspect/verify/process fixtures from the
                                    live measurement of its archived workdir (not by hand)
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


def _measure(ids: list[str], archive: str | None, as_json: bool, opinion: str = "vision") -> int:
    """The fixture comparison for the OpenCV 5 measurements: the live measurer's numbers
    beside the fixture's, for every finding and gate, with the disagreements marked."""
    from .backends.cached import CachedBackend, FixtureMissing
    from .measure import ArchiveMeasurer, ArchiveMissing
    from .models import to_dict
    from .vision import require_cv2

    cv2 = require_cv2()
    demo = CachedBackend()
    m = ArchiveMeasurer(archive, opinion=opinion)
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


def _aws(a) -> int:
    from pathlib import Path
    from .aws import AWS, BUCKET, FUNCTION, REGION
    from .backends.cached import CachedBackend
    from .measure import archive_root
    aws = AWS()
    if a.what == "status":
        ident = aws.identity()
        print(f"  region {REGION} · bucket {BUCKET}: {aws.bucket_status()} · identity: {ident['arn_type']} {ident['principal']} in account {ident['account']}")
        try:
            c = aws.lam().get_function_configuration(FunctionName=FUNCTION)
            print(f"  lambda {FUNCTION}: {c['Runtime']} {c['Architectures'][0]} {c['MemorySize']} MB, timeout {c['Timeout']} s, layers {len(c.get('Layers', []))}, last modified {c['LastModified']}")
        except Exception as e:  # noqa: BLE001
            print(f"  lambda {FUNCTION}: not deployed ({type(e).__name__})")
        demo = CachedBackend()
        for c in demo.clips():
            if c.archive.get("workdir"):
                sha = c.recognize["sha256"] if isinstance(c.recognize["sha256"], str) else c.recognize["sha256"][0]
                print(f"  {c.id:<6} {sha[:12]}… {'on S3' if aws.recognize(sha) else 'not on S3'}")
        return 0
    if a.what == "sync":
        print(f"  bucket: {aws.ensure_bucket()}")
        root = archive_root(a.archive)
        demo = CachedBackend()
        for cid in a.clips or [c.id for c in demo.clips() if c.archive.get('workdir')]:
            c = demo.clip(cid)
            r = aws.sync_clip(c, root, progress=lambda n, t: print(f"    … {n} files", flush=True))
            print(f"  {cid}: sha {r['sha256'][:12]}… uploaded {r['uploaded']}, skipped {r['skipped']} (same size), {r['bytes'] / 1e6:.0f} MB")
        print(f"  model: s3://{BUCKET}/{aws.sync_model()}")
        return 0
    if a.what in ("web-deploy", "web-publish", "web-invalidate"):
        from .deploy_web import _state, deploy, invalidate, publish_static
        if a.what == "web-publish":
            r = publish_static(aws); print(f"  static + media: uploaded {r['uploaded']}, skipped {r['skipped']}")
            st = _state()
            if st.get("distribution_id"):
                print(f"  invalidation {invalidate(aws, st['distribution_id'])} on {st['domain']}")
            return 0
        if a.what == "web-invalidate":
            st = _state(); print(f"  invalidation {invalidate(aws, st['distribution_id'])} on {st['domain']}"); return 0
        r = deploy(aws)
        print(f"  static + media: uploaded {r['static']['uploaded']}, skipped {r['static']['skipped']}")
        print(f"  api lambda: {r['function']} · {r['function_url']}")
        print(f"  cloudfront: {r['distribution_id']} · {r.get('status', '')}")
        print(f"  URL: {r['url']}")
        return 0
    if a.what == "deploy":
        print(f"  bucket: {aws.ensure_bucket()}")
        role = aws.ensure_role(); print(f"  role: {role}")
        if a.layer:
            layer = aws.deploy_layer(Path(a.layer)); print(f"  layer: {layer}")
        else:
            vs = aws.lam().list_layer_versions(LayerName="stage-ready-opencv5").get("LayerVersions", [])
            if not vs:
                print("  no layer published yet: pass --layer <dir with python/ and bin/>"); return 2
            layer = vs[0]["LayerVersionArn"]; print(f"  layer (existing): {layer}")
        fn = aws.deploy_function(layer, role); print(f"  function: {fn}")
        for r in aws.trace.records:
            print(f"    {r['service']} {r.get('op')} request {r.get('request_id')}")
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stage_ready")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=8765); s.add_argument("--host", default="127.0.0.1")
    r = sub.add_parser("run"); r.add_argument("clips", nargs="*"); r.add_argument("--live", action="store_true")
    t = sub.add_parser("trace"); t.add_argument("clips", nargs="*"); t.add_argument("--live", action="store_true")
    m = sub.add_parser("measure"); m.add_argument("clips", nargs="*"); m.add_argument("--archive", default=None); m.add_argument("--json", action="store_true"); m.add_argument("--opinion", default="vision", choices=["vision", "dnn"])
    b = sub.add_parser("bundle"); b.add_argument("clips", nargs="*"); b.add_argument("--out", default=None); b.add_argument("--archive", default=None)
    b.add_argument("--dry-run", action="store_true"); b.add_argument("--install", default=None); b.add_argument("--verify", default=None)
    r_ = sub.add_parser("record"); r_.add_argument("clip"); r_.add_argument("--archive", default=None); r_.add_argument("--fixed", action="store_true"); r_.add_argument("--out", default=None)
    aw = sub.add_parser("aws"); aw.add_argument("what", choices=["status", "sync", "deploy", "web-deploy", "web-publish", "web-invalidate"]); aw.add_argument("clips", nargs="*"); aw.add_argument("--layer", default=None); aw.add_argument("--archive", default=None)
    ae = sub.add_parser("agent-eval"); ae.add_argument("--model", default=None); ae.add_argument("--repeat", type=int, default=1); ae.add_argument("--clips", nargs="*"); ae.add_argument("--json", action="store_true")
    mo = sub.add_parser("models"); mo.add_argument("what", nargs="?", default="list", choices=["list", "fetch"]); mo.add_argument("name", nargs="?", default=None)
    ev = sub.add_parser("evaluate"); ev.add_argument("--agent", default="bedrock", choices=["bedrock", "rules"]); ev.add_argument("--items", nargs="*"); ev.add_argument("--prepare", action="store_true")
    ev.add_argument("--report", action="store_true"); ev.add_argument("--archive", default=None); ev.add_argument("--opinion", default="dnn", choices=["vision", "dnn"])
    sc = sub.add_parser("segcheck"); sc.add_argument("clips", nargs="*"); sc.add_argument("--archive", default=None); sc.add_argument("--no-crop", action="store_true"); sc.add_argument("--json", action="store_true"); sc.add_argument("--model", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "evaluate":
        from .evaluate import evaluate
        from .eval_report import write_report
        if not a.report or a.items or a.prepare:
            s_ = evaluate(a.agent, a.items, a.prepare, a.archive, a.opinion)
            print(f"  {s_['agent']}: {s_['outcome_ok']}/{s_['n']} outcomes as labelled · silently wrong {len(s_['silently_wrong'])} {s_['silently_wrong']} · missed {s_['missed_defects'] or '-'}")
        if a.report:
            print(f"  report: {write_report()}")
        return 0
    if a.cmd == "aws":
        return _aws(a)
    if a.cmd == "agent-eval":
        from .agent_eval import evaluate, print_report
        from .aws import BEDROCK_MODEL
        res = evaluate(a.model or BEDROCK_MODEL, a.repeat, a.clips or None)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print_report(res)
        return 0 if res["summary"]["pass"] == res["summary"]["calls"] else 1
    if a.cmd == "models":
        from .vision.segment import DEFAULT_MODEL, MODELS, MODELS_DIR, fetch, sha256_of
        if a.what == "fetch":
            p = fetch(a.name or DEFAULT_MODEL); print(f"  {p} ({p.stat().st_size / 1e6:.0f} MB, sha256 {sha256_of(p)[:16]}…)")
            return 0
        for name, spec in MODELS.items():
            p = MODELS_DIR / spec["file"]
            state = "present" if p.is_file() and sha256_of(p) == spec["sha256"] else ("present, hash differs" if p.is_file() else "not downloaded")
            print(f"  {name:<18} {spec['input'][0]}×{spec['input'][1]}  {spec['license']:<48} {state}{'  (default)' if name == DEFAULT_MODEL else ''}\n{'':20}{spec['source']}")
        return 0
    if a.cmd == "segcheck":
        from .vision.segcheck import run as segcheck
        segcheck(a.clips or None, a.archive, crop=not a.no_crop, as_json=a.json, model=a.model)
        return 0

    if a.cmd == "record":
        from pathlib import Path
        from .record import record
        for p in record(a.clip, a.archive, a.fixed, Path(a.out) if a.out else None):
            print(f"  wrote {p}")
        return 0
    if a.cmd == "measure":
        return _measure(a.clips, a.archive, a.json, a.opinion)
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
        if a.live and hasattr(backend, "flush"):
            fl = backend.flush()
            if fl:
                summ = fl.get("summary", {})
                print(f"  ◦ trace {fl.get('local')}" + (f" · {fl.get('s3')}" if fl.get("s3") else ""))
                print(f"    latency ms {summ.get('latency_ms')} · bedrock tokens {summ.get('bedrock_tokens')} · errors {len(summ.get('errors', []))}")
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
