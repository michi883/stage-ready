"""A small HTTP server: the UI, the profile, the clips, and a run streamed as SSE.

    GET /                         the screen (web/index.html)
    GET /api/profile              the Target Output Profile
    GET /api/clips?demo=1         the clips the backend knows
    GET /api/recognize?demo=1&sha256=<hex>&name=<file>
                                  match an upload to a known clip (the file itself is never sent;
                                  the browser fingerprints it) → {"clip": …, "matched_by": …} or null
    GET /api/run/<clip>?demo=1    server-sent events: one per loop event, then `end`
                                  &budget=N overrides the profile's retry budget (0 shows the reshoot exit)
    GET /stills/<clip>/<file>     optional real stills and videos in demo/clips/<clip>/stills/
                                  (byte ranges honoured, so <video> can seek and loop)

Standard library only, so demo mode has no dependencies. Each SSE stream runs the loop in
its own thread; three clips are three independent runs, as they would be live.
"""
from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .backends import get_backend
from .backends.cached import FixtureMissing
from .loop import run
from .profile import Profile

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
CLIPS = ROOT / "demo" / "clips"


class Handler(BaseHTTPRequestHandler):
    server_version = "StageReady/0.1"

    def log_message(self, fmt, *args):  # quieter console: only the API, never the media or the stream
        if "/api/run/" in str(args[0]) or "/api/" not in str(args[0]):
            return
        super().log_message(fmt, *args)

    # ---- helpers ------------------------------------------------------------------------
    def _json(self, obj, status=HTTPStatus.OK):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        if not path.is_file():
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range", "")
        partial = rng.startswith("bytes=") and size > 0
        if partial:                                  # one range, "bytes=a-b" | "bytes=a-" | "bytes=-n"
            a, _, b = rng[6:].partition("-")
            if a:
                start, end = int(a), (int(b) if b else size - 1)
            else:
                start = max(0, size - int(b))
            end = min(end, size - 1)
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with path.open("rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _demo(self, q) -> bool:
        # No query means the demo: the cached, deterministic replay. `?demo=0` is the live hybrid.
        return q.get("demo", ["1"])[0] in ("1", "true", "yes")

    # ---- routes -------------------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path

        if path == "/api/profile":
            return self._json(Profile.load().data)

        if path == "/api/clips":
            try:
                backend = get_backend(self._demo(q))
                return self._json([json.loads(json.dumps(c.__dict__)) for c in backend.clips()])
            except NotImplementedError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_IMPLEMENTED)

        if path == "/api/recognize":
            try:
                backend = get_backend(self._demo(q))
                clip = backend.recognize(sha256=q.get("sha256", [None])[0], name=q.get("name", [None])[0])
            except NotImplementedError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_IMPLEMENTED)
            if clip is None:
                return self._json({"clip": None, "matched_by": None})
            return self._json({"clip": json.loads(json.dumps(clip.__dict__)), "matched_by": clip.recognize.get("matched_by")})

        if path.startswith("/api/run/"):
            budget = q.get("budget", [None])[0]
            return self._run(path.split("/")[3], self._demo(q), int(budget) if budget is not None else None)

        if path.startswith("/stills/"):
            parts = path.split("/")
            if len(parts) == 4 and ".." not in path:
                return self._file(CLIPS / parts[2] / "stills" / parts[3])
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        if path == "/":
            return self._file(WEB / "index.html")
        rel = path.lstrip("/")
        if ".." not in rel and (WEB / rel).is_file():
            return self._file(WEB / rel)
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _run(self, clip_id: str, demo: bool, budget: int | None = None):
        try:
            backend = get_backend(demo)
            clip = backend.clip(clip_id)
        except NotImplementedError as e:
            return self._json({"error": str(e)}, HTTPStatus.NOT_IMPLEMENTED)
        except FixtureMissing as e:
            return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
        profile = Profile.load()
        if budget is not None:                      # demo lever: the other exit (README, roadmap milestone 6)
            profile.data["retry_budget"] = budget

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        # The loop runs in its own thread and its events come through a queue, so the stream can
        # send a keepalive comment every few seconds while a live stage (a two-minute Lambda
        # verification) produces nothing — proxies and CDNs close an idle response otherwise.
        import queue
        import threading
        q_: "queue.Queue[tuple[str, object]]" = queue.Queue()

        def produce():
            try:
                for ev in run(clip, profile, backend):
                    q_.put(("event", ev))
                if hasattr(backend, "flush"):            # the live run's observability record: request ids, latencies, decisions
                    fl = backend.flush()
                    if fl:
                        q_.put(("event", {"type": "trace", "clip": clip_id, **fl}))
            except (FixtureMissing, NotImplementedError, RuntimeError) as e:
                q_.put(("event", {"type": "error", "clip": clip_id, "message": str(e)}))
            except Exception as e:  # noqa: BLE001 — the stream must end, with the reason
                q_.put(("event", {"type": "error", "clip": clip_id, "message": f"{type(e).__name__}: {e}"}))
            q_.put(("end", None))

        threading.Thread(target=produce, daemon=True).start()
        try:
            while True:
                try:
                    kind, ev = q_.get(timeout=10)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n"); self.wfile.flush()
                    continue
                if kind == "end":
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    break
                self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        try:
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def serve(host: str = "127.0.0.1", port: int = 8765) -> int:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Stage Ready — demo at http://{host}:{port}/?demo=1")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
