"""AWS Lambda entry point: INSPECT or VERIFY, with OpenCV 5, from a workdir on S3.

    event = {"op": "inspect" | "verify", "clip": {<Clip fields, archive block in S3 terms>},
             "profile": {<the Target Output Profile's data>}, "target": "source" | "artifact": "attempt_1",
             "opinion": "vision" | "dnn", "run_id": "…"}

The function mirrors `work/<sha>/`, `sources/<sha>/` and the named `artifacts/<sha>/` objects into
`/tmp/archive` (kept across warm invocations, keyed by size), fetches the segmenter's weights into
`/tmp/models` when the DNN opinion is asked for, and runs `ArchiveMeasurer` exactly as it runs on
the laptop. The record goes back in the response and to `measurements/<sha>/…` in the bucket.

Runtime: the `stage-ready-opencv5` layer (opencv-python-headless 5.0.0.93, numpy 2.4.6, a static
ffmpeg for the audio hash) on Python 3.12 / arm64. Credentials: the function's role, never a key.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ARCHIVE = Path("/tmp/archive")
MODELS = Path(os.environ.get("STAGE_READY_MODELS_DIR", "/tmp/models"))
BUCKET = os.environ.get("STAGE_READY_BUCKET", "stage-ready-videos")
_COLD = {"cold": True}


def _sync_prefix(s3, prefix: str, dest_root: Path, workers: int = 32) -> int:
    """Mirror s3://bucket/<prefix>/ into dest_root/<prefix>/, skipping same-size files. The
    workdir is thousands of small mattes, so the downloads run in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    todo = []
    token = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": prefix.rstrip("/") + "/"}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            dst = dest_root / o["Key"]
            if not (dst.exists() and dst.stat().st_size == o["Size"]):
                todo.append((o["Key"], dst))
        if not r.get("IsTruncated"):
            break
        token = r.get("NextContinuationToken")
    for _, dst in todo:
        dst.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda kd: s3.download_file(BUCKET, kd[0], str(kd[1])), todo))
    return len(todo)


def _fetch_key(s3, key: str, dest: Path) -> bool:
    if dest.exists():
        h = s3.head_object(Bucket=BUCKET, Key=key)
        if dest.stat().st_size == h["ContentLength"]:
            return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(BUCKET, key, str(dest))
    return True


def handler(event, context):
    import boto3
    from stage_ready.measure import ArchiveMeasurer
    from stage_ready.models import Clip, to_dict
    from stage_ready.profile import Profile

    t0 = time.time()
    cold = _COLD.pop("cold", False)
    s3 = boto3.client("s3")
    op = event["op"]
    clip = Clip(**event["clip"])
    profile = Profile(event["profile"])
    opinion = event.get("opinion", "vision")
    sha = clip.archive["workdir"].split("/")[-1]

    # ---- mirror what the measurement reads
    n = _sync_prefix(s3, clip.archive["workdir"], ARCHIVE)
    n += int(_fetch_key(s3, clip.archive["source"], ARCHIVE / clip.archive["source"]))
    if op == "verify":
        spec = clip.archive["artifacts"][event["artifact"]]
        if spec.get("video"):
            n += int(_fetch_key(s3, spec["video"], ARCHIVE / spec["video"]))
    if opinion == "dnn":
        from stage_ready.vision.segment import MODELS as SEG_MODELS, DEFAULT_MODEL
        f = SEG_MODELS[DEFAULT_MODEL]["file"]
        n += int(_fetch_key(s3, f"models/{f}", MODELS / f))
    t_sync = time.time()

    # ---- measure, exactly as on the laptop
    m = ArchiveMeasurer(ARCHIVE, opinion=opinion)
    if op == "inspect":
        rec = to_dict(m.inspect(clip, event.get("target", "source"), profile))
        key = f"measurements/{sha}/inspect.{event.get('target', 'source')}.json"
    elif op == "verify":
        rec = to_dict(m.verify(clip, event["artifact"], profile))
        key = f"measurements/{sha}/verify.{event['artifact']}.json"
    else:
        raise ValueError(f"unknown op {op!r}")
    t_meas = time.time()
    rec["provenance"] = (f"measured on AWS Lambda {os.environ.get('AWS_REGION', '')} ({context.function_name if context else 'local'}, "
                         f"request {context.aws_request_id if context else '-'}): OpenCV 5 over s3://{BUCKET}/{clip.archive['workdir']}"
                         + (f", DNN second opinion" if opinion == "dnn" else "") + f"; {rec.get('provenance', '')}")
    rec["aws"] = {"request_id": context.aws_request_id if context else None, "function": context.function_name if context else None,
                  "region": os.environ.get("AWS_REGION"), "cold": cold, "synced_files": n,
                  "sync_ms": int((t_sync - t0) * 1000), "measure_ms": int((t_meas - t_sync) * 1000), "run_id": event.get("run_id")}
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(rec, ensure_ascii=False, indent=1).encode(), ContentType="application/json")
    rec["s3_key"] = key
    rec["lambda_ms"] = int((time.time() - t0) * 1000); rec["sync_ms"] = rec["aws"]["sync_ms"]; rec["measure_ms"] = rec["aws"]["measure_ms"]; rec["cold"] = cold
    return rec
