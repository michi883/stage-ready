"""Include the public runtime data in wheels without redistributing performer media."""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithAssets(build_py):
    def run(self):
        super().run()
        root = Path(__file__).parent
        assets = Path(self.build_lib) / "stage_ready" / "_data"
        if assets.exists():
            shutil.rmtree(assets)  # Never retain removed fixtures from an earlier wheel build.
        for pattern in ("profiles/*.json", "web/*.html", "web/*.js", "web/*.css",
                        "demo/*.json", "demo/clips/*/*.json", "demo/eval/**/*.json",
                        "demo/eval/*.md"):
            for source in sorted(root.glob(pattern)):
                target = assets / source.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                self.copy_file(str(source), str(target))


setup(cmdclass={"build_py": BuildWithAssets})
