"""Deployment payload includes the SDK and fixtures, never performer media."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from stage_ready.deploy_web import _web_zip


class DeploymentPackage(unittest.TestCase):
    def test_web_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            (sdk / "boto3").mkdir()
            (sdk / "boto3" / "__init__.py").write_text("# test SDK marker\n")
            with patch.dict("os.environ", {"STAGE_READY_SDK_DIR": str(sdk)}):
                payload = _web_zip()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                for name in ("run.sh", "boto3/__init__.py", "stage_ready/server.py", "web/index.html",
                             "profiles/midtown_red_curtain.json", "demo/lineup.json", "demo/clips/ethel/clip.json"):
                    self.assertIn(name, names)
                self.assertFalse(any("stills/" in name or name.endswith((".mp4", ".mov", ".onnx", ".pyc")) for name in names))
                self.assertTrue(archive.getinfo("run.sh").external_attr >> 16 & 0o111)

    def test_missing_sdk_is_an_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"STAGE_READY_SDK_DIR": directory}):
                with self.assertRaisesRegex(FileNotFoundError, "scripts/build_lambda.py"):
                    _web_zip()
