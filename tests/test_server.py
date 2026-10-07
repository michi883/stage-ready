"""Exercise the actual HTTP/SSE boundary without AWS or performer media."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from stage_ready.server import Handler, ThreadingHTTPServer


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path, headers=None):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            conn.request("GET", path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_workspace_and_assets(self):
        for path, content_type in (("/", "text/html"), ("/app.js", "javascript"), ("/style.css", "text/css")):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertIn(content_type, headers["Content-Type"])
                self.assertTrue(body)

    def test_picker_and_unknown_clip(self):
        status, _, body = self.get("/api/clips")
        self.assertEqual(status, 200)
        self.assertEqual([c["id"] for c in json.loads(body)], ["brian_padded", "ethel", "zach"])
        self.assertEqual(self.get("/api/run/unknown")[0], 404)

    def test_sse_recovery_and_completion(self):
        status, headers, body = self.get("/api/run/ethel")
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers["Content-Type"])
        self.assertTrue(body.endswith(b"event: end\ndata: {}\n\n"))
        events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith(b"data: ")][:-1]
        self.assertEqual(events[-1]["outcome"], "delivered")
        self.assertIn("reprocess", events[-1]["path"])

    def test_invalid_budget_and_clip_fail_before_stream(self):
        for suffix in ("ethel?budget=no", "ethel?budget=-1", "ethel?budget=999", "", "../ethel", "ethel/extra"):
            with self.subTest(suffix=suffix):
                status, headers, _ = self.get("/api/run/" + suffix)
                self.assertEqual(status, 400)
                self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(self.get("/api/run/ethel?budget=0")[0], 200)

    def test_media_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.bin").write_bytes(b"0123456789")
            with patch("stage_ready.server.WEB", root):
                for value, expected in (("bytes=2-5", b"2345"), ("bytes=8-", b"89"), ("bytes=-3", b"789")):
                    status, headers, body = self.get("/sample.bin", {"Range": value})
                    self.assertEqual(status, 206)
                    self.assertEqual(body, expected)
                    self.assertEqual(int(headers["Content-Length"]), len(expected))
                for value in ("bytes=garbage", "bytes=-", "bytes=0-1,3-4", "bytes=1-" + "9" * 21):
                    self.assertEqual(self.get("/sample.bin", {"Range": value})[0], 400)
                for value in ("bytes=99-", "bytes=-0", "bytes=5-2"):
                    self.assertEqual(self.get("/sample.bin", {"Range": value})[0], 416)

    def test_no_repository_file_exposure(self):
        for path in ("/.env", "/../pyproject.toml", "/stills/../clip.json"):
            self.assertEqual(self.get(path)[0], 404)
