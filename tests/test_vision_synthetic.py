"""Real OpenCV measurements on generated input: no private archive or model required."""
from pathlib import Path
import tempfile
import unittest

from stage_ready.vision import OpenCVMissing, require_cv2

try:
    cv2 = require_cv2()
except OpenCVMissing:
    cv2 = None


@unittest.skipUnless(cv2 is not None, "install requirements/headless.txt to exercise OpenCV 5")
class GeneratedVideo(unittest.TestCase):
    def test_picture_area_and_decoded_frame_count(self):
        import numpy as np
        from stage_ready.vision.band import detect_band
        from stage_ready.vision.media import frame_count, probe
        with tempfile.TemporaryDirectory() as directory:
            for number in range(1, 5):
                frame = np.zeros((120, 160, 3), dtype=np.uint8)
                frame[16:104, 16:144] = 120 + number
                self.assertTrue(cv2.imwrite(str(Path(directory) / f"frame_{number:04d}.png"), frame))
            source = str(Path(directory) / "frame_%04d.png")
            band = detect_band(source, step=1)
            self.assertEqual((band.w, band.h, band.x, band.y), (128, 88, 16, 16))
            self.assertEqual(band.frames_sampled, 4)
            self.assertFalse(band.fills_file)
            self.assertEqual(frame_count(source), 4)
            info = probe(source)
            self.assertEqual((info.width, info.height), (160, 120))
