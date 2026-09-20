#!/bin/bash
# ============================================================================
#  The evaluation set's synthesised inputs — one known defect each, from a clean base.
#
#    demo/eval/derive_eval.sh [archive-dir]        (default: $STAGE_READY_ARCHIVE or ~/mts)
#
#  These are NOT demo inputs. They are negatives for `python3 -m stage_ready evaluate`
#  (demo/eval/set.json labels them): a recording that verifies on its own — Brian's, untouched,
#  2.91× / head 0.7 % on 2026-09-20 — with exactly one capture or delivery defect injected, so the
#  loop's answer can be scored against a label that is known by construction. Where a defect can
#  only be injected by touching the performer's pixels (under-exposure), the file lives here and
#  nowhere near the demo. Every command is below; evaluate.py records each output's SHA-256.
#
#  Input-side (a wrong recording arrives):
#    brian_zoomed        too close — the picture cropped to head and chest (no resampling)
#    brian_crown_cut     the crown cut off by the top of the picture on every frame (top 120 rows removed)
#    brian_underlit      a dark room — linear gain ×0.35 on the whole picture
#    tehila_45s          a real recording, trimmed to 45 s (the corpus's long take)
#  Output-side (a wrong delivery is produced — the gates must catch it):
#    gate_frame_drop     Brian's delivery with one frame removed (1284 ≠ 1285)
#    gate_audio_reencoded  Brian's delivery with its audio re-encoded (MD5 differs)
#    gate_frozen_frames  Brian's delivery with frames 600–629 replaced by frame 600 (count intact)
# ============================================================================
set -euo pipefail
ARCHIVE="${1:-${STAGE_READY_ARCHIVE:-$HOME/mts}}"
cd "$ARCHIVE"
mkdir -p eval
X="-c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -movflags +faststart"

# ---- input-side negatives, from Brian's untouched recording ---------------------------------------
[ -f eval/brian_zoomed.mp4 ]     || ffmpeg -v error -y -i brian_shirley_v2.mp4 -vf "crop=1056:600:337:0" $X -c:a copy eval/brian_zoomed.mp4
[ -f eval/brian_crown_cut.mp4 ]  || ffmpeg -v error -y -i brian_shirley_v2.mp4 -vf "crop=1920:960:0:120" $X -c:a copy eval/brian_crown_cut.mp4
[ -f eval/brian_underlit.mp4 ]   || ffmpeg -v error -y -i brian_shirley_v2.mp4 -vf "lutrgb=r=val*0.35:g=val*0.35:b=val*0.35" $X -c:a copy eval/brian_underlit.mp4
# ---- a real long take, bench-sized -----------------------------------------------------------------
[ -f eval/tehila_45s.mp4 ]       || ffmpeg -v error -y -t 45 -i tehila.mp4 $X -c:a copy eval/tehila_45s.mp4

# ---- output-side negatives, from Brian's delivery (the render of the untouched recording) ------------
R=brian_shirley_v2_base_red_v1.mp4
[ -f eval/gate_frame_drop.mp4 ]       || ffmpeg -v error -y -i $R -vf "select=not(eq(n\,600)),setpts=N/FRAME_RATE/TB" -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -c:a copy -movflags +faststart eval/gate_frame_drop.mp4
[ -f eval/gate_audio_reencoded.mp4 ]  || ffmpeg -v error -y -i $R -c:v copy -c:a aac -b:a 128k -movflags +faststart eval/gate_audio_reencoded.mp4
if [ ! -f eval/gate_frozen_frames.mp4 ]; then
  # frames 600–629 replaced by frame 600: the count and the audio are intact; only the motion is wrong.
  # Decoded and re-written frame by frame (OpenCV → rawvideo → x264), the audio stream copied.
  python3 - <<'PY'
import cv2, subprocess
src = "brian_shirley_v2_base_red_v1.mp4"
c = cv2.VideoCapture(src); W = int(c.get(3)); H = int(c.get(4)); fps = c.get(5)
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps:.6f}", "-i", "-", "-i", src,
                      "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                      "eval/gate_frozen_frames.mp4"], stdin=subprocess.PIPE)
n = 0; frozen = None
while True:
    ok, f = c.read()
    if not ok: break
    if n == 600: frozen = f.copy()
    p.stdin.write((frozen if 600 <= n <= 629 else f).tobytes()); n += 1
p.stdin.close(); p.wait()
PY
fi
for f in eval/*.mp4; do printf "%-32s " "$f"; ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=width,height,nb_read_frames -of csv=p=0 "$f" | tr '\n' ' '; shasum -a 256 "$f" | cut -c1-12; done
