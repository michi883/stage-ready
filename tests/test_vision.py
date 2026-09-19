"""The OpenCV 5 port reproduces the archived measurements (PLAN.md step 2a's accept test).

Needs OpenCV 5 (`pip install -e '.[live]'`) and the Red Curtain archive ($STAGE_READY_ARCHIVE,
default ~/mts). Without either it skips — the demo suite in test_demo.py never needs them.
`python3 -m stage_ready measure` prints the full comparison; this pins the numbers the demo's
story rests on.
"""
import os
import unittest
from pathlib import Path

from stage_ready.backends.cached import CachedBackend
from stage_ready.profile import Profile

try:
    from stage_ready.vision import require_cv2
    require_cv2()
    HAVE_CV2 = True
except Exception:                                   # ImportError or OpenCVMissing
    HAVE_CV2 = False

ARCHIVE = Path(os.path.expanduser(os.environ.get("STAGE_READY_ARCHIVE", "~/mts")))
HAVE_ARCHIVE = (ARCHIVE / "work" / "midtown_ethel_chadwick_v2" / "affine.csv").exists()


@unittest.skipUnless(HAVE_CV2, "OpenCV 5 not installed (pip install -e '.[live]')")
class Pins(unittest.TestCase):
    def test_refuses_opencv_4(self):
        from stage_ready import vision
        import cv2
        real = cv2.__version__
        try:
            cv2.__version__ = "4.11.0"
            with self.assertRaises(vision.OpenCVMissing):
                vision.require_cv2()
        finally:
            cv2.__version__ = real


@unittest.skipUnless(HAVE_CV2 and HAVE_ARCHIVE, "needs OpenCV 5 and the Red Curtain archive")
class ReproducesTheArchive(unittest.TestCase):
    """Every number the demo shows for Ethel, recomputed from her files with OpenCV 5."""

    @classmethod
    def setUpClass(cls):
        from stage_ready.measure import ArchiveMeasurer
        cls.m = ArchiveMeasurer(ARCHIVE)
        cls.demo = CachedBackend()
        cls.profile = Profile.load()
        cls.clip = cls.demo.clip("ethel")

    def assertClose(self, a, b, tol=0.02, msg=""):
        self.assertLessEqual(abs(a - b), max(tol * abs(a), 0.006), f"{msg}: fixture {a} vs live {b}")

    def test_inspect_source_matches_the_fixture(self):
        live = {f.id: f for f in self.m.inspect(self.clip, "source", self.profile).findings}
        for f in self.demo.inspect(self.clip, "source", self.profile, None).findings:
            if f.id not in live and f.status == "info":
                continue        # wardrobe_vs_plate: the pre-composite predictor, info only; not ported (it does not discriminate)
            self.assertEqual(f.status, live[f.id].status, f.id)
            a, b = f.value, live[f.id].value
            if isinstance(a, dict):
                for k in a:
                    if isinstance(a[k], (int, float)) and k in b:
                        self.assertClose(a[k], b[k], msg=f"{f.id}.{k}")
            elif isinstance(a, (int, float)):
                self.assertClose(a, b, msg=f.id)

    def test_attempt_2_separation_is_the_measured_1_52(self):
        v = self.m.verify(self.clip, "attempt_2", self.profile)
        self.assertTrue(v.passed, [g.id for g in v.failing])
        g = {x.id: x for x in v.gates}
        self.assertEqual(g["separation"].value, 1.52)
        self.assertEqual((v.measurements["edge_luma_in"], v.measurements["edge_luma_out"]), (0.188, 0.123))
        self.assertEqual(g["head_spread"].value, 0.013)
        self.assertEqual(g["frame_count"].value, 1237)
        self.assertEqual(g["audio_md5"].value, "equal")
        fx = {x.id: x for x in self.demo.verify(self.clip, "attempt_2", self.profile, None).gates}
        for gid in fx:
            self.assertEqual(fx[gid].status, g[gid].status, gid)

    def test_attempt_1_fails_separation_from_the_delivered_file(self):
        # attempt 1's composite frames are gone (overwritten by the shadow-lift render); the
        # delivered H.264 file measures the same 1.13x the archive recorded from the frames.
        v = self.m.verify(self.clip, "attempt_1", self.profile)
        self.assertEqual([g.id for g in v.failing], ["separation"])
        self.assertEqual({x.id: x for x in v.gates}["separation"].value, 1.13)


if __name__ == "__main__":
    unittest.main()
