"""OpenCV 5 does the seeing.

The measurements the loop's INSPECT and VERIFY are made of, ported from the Red Curtain
archive's scripts (`tools/detect_band.py`, `pose_qc.py`, `matte_qc.py`, `silhouette_qc.py`,
and the head-height part of `track_frame.py`) so the numbers are computed here, from the files,
rather than replayed. Each module keeps the archive script's arithmetic to the digit — the
fixtures under `demo/clips/` were measured with those scripts, and `python3 -m stage_ready
measure` shows the two agreeing (README, "What is measured").

    band.detect_band     the picture area inside a padded file          → picture_area
    pose.pose_qc         one subject, steady distance, size in frame    → pose_coverage, one_subject,
                                                                          distance_steady, subject_size
    matte.matte_extent   the matte against an independent silhouette   → matte_extent
    matte.crown_cut      how often the crown leaves the picture         → headroom
    silhouette.separation  performer vs stage, in luminance alone      → separation
    track.head_height    the head's height on the canvas, per frame    → head_spread, head_drift
    media.frame_count / audio_md5 / probe                              → frame_count, audio_md5

`cv2` is imported inside the functions, not here: demo mode (`?demo=1`) never touches this
package and must not need OpenCV installed. Everything that does need it goes through
`require_cv2()`, which refuses anything older than OpenCV 5 — the competition rule, and the
version every fixture was measured with (`opencv-python==5.0.0.93`, pinned in pyproject.toml).
"""
from __future__ import annotations


class OpenCVMissing(RuntimeError):
    pass


def require_cv2():
    """The `cv2` module, or a clear refusal. Nothing in this package works on OpenCV 4."""
    try:
        import cv2
    except ImportError as e:  # pragma: no cover
        raise OpenCVMissing("OpenCV 5 is required for live measurement: pip install -e '.[live]' "
                            "(demo mode does not need it)") from e
    major = int(cv2.__version__.split(".")[0])
    if major < 5:
        raise OpenCVMissing(f"OpenCV {cv2.__version__} found; the measurements are pinned to OpenCV 5 "
                            f"(pip install -e '.[live]')")
    return cv2


from .band import Band, detect_band                       # noqa: E402
from .pose import PoseQC, pose_qc, read_pose              # noqa: E402
from .matte import MatteQC, crown_cut, matte_extent       # noqa: E402
from .silhouette import Separation, separation            # noqa: E402
from .track import HeadHeight, head_height                # noqa: E402
from .media import Probe, audio_md5, frame_count, probe   # noqa: E402

__all__ = ["require_cv2", "OpenCVMissing",
           "Band", "detect_band", "PoseQC", "pose_qc", "read_pose", "MatteQC", "matte_extent", "crown_cut",
           "Separation", "separation", "HeadHeight", "head_height", "Probe", "probe", "frame_count", "audio_md5"]
