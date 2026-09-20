# models/

The DNN segmentation weights `stage_ready/vision/segment.py::SubjectSegmenter` loads with
`cv2.dnn.readNet`. Not committed (6 MB and 176 MB); fetched with a SHA-256 check:

    python3 -m stage_ready models            # what is registered, and what is present
    python3 -m stage_ready models fetch      # the default (u2net_human_seg)
    python3 -m stage_ready models fetch pphumanseg

| name | file | input | license | source |
|---|---|---|---|---|
| `u2net_human_seg` (default) | `u2net_human_seg.onnx` | 320×320 | Apache-2.0 | U²-Net (xuebinqin/U-2-Net) human-segmentation weights, ONNX export hosted by rembg |
| `pphumanseg` | `human_segmentation_pphumanseg_2023mar.onnx` | 192×192 | Apache-2.0 | OpenCV Zoo, ported from PaddleHub |

Which one and why: `python3 -m stage_ready segcheck --model <name>` and README, "Why OpenCV 5".
