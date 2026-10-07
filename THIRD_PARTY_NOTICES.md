# Third-party components and media

Stage Ready's own source is provided under the [MIT license](LICENSE). Dependency packages,
model weights, and performer recordings retain their own terms; the code license does not
relicense them.

| Component | Use / upstream |
| --- | --- |
| OpenCV 5 | Image/video analysis and DNN inference; [OpenCV](https://github.com/opencv/opencv), Apache-2.0 |
| NumPy | Numerical operations; [NumPy](https://github.com/numpy/numpy), BSD-3-Clause |
| boto3 / botocore / s3transfer | AWS access; [AWS SDK for Python](https://github.com/boto/boto3), Apache-2.0; see each installed distribution's license |
| U²-Net human segmentation | DNN second opinion; [U²-Net](https://github.com/xuebinqin/U-2-Net), Apache-2.0; ONNX export distributed by [rembg](https://github.com/danielgatis/rembg) |
| PP-HumanSeg | Optional alternative; [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg), Apache-2.0 |
| AWS Lambda Web Adapter | Streaming HTTP API on Lambda; [upstream](https://github.com/awslabs/aws-lambda-web-adapter), Apache-2.0 |
| FFmpeg | Decoded-audio hashes and local media processing; [FFmpeg licensing](https://ffmpeg.org/legal.html), LGPL/GPL depending on the supplied build |

Weights and FFmpeg binaries are not included in the repository or Python distributions.
`python -m stage_ready models fetch` verifies the registered model SHA-256 before accepting it.
If redistributing a deployment layer or model, preserve upstream notices and check the terms
of the specific binaries. Transitive dependency licenses are retained in the vendored SDK's
distribution metadata.

BodyTrack, MatAnyone, Apple Vision, and Composite are components of the external Red Curtain
preparation/rendering pipeline; they are not shipped in this repository. The submitted code
measures prepared workdirs and uses cache-backed renders. See the
[technical report](TECHNICAL_REPORT.md#what-comes-from-the-red-curtain-pipeline) for provenance.

Performer media is excluded from source control and distribution packages. Names, measured
fixtures, hashes, and evaluation records describe the demonstration inputs. Permission to
review a private judge bundle does not imply permission to redistribute its footage.
