"""Locate runtime assets in a checkout, Lambda bundle, or installed wheel."""
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE / "_data" if (PACKAGE / "_data").is_dir() else PACKAGE.parent
