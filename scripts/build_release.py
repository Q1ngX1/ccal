from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "ccal"


def _find_tesseract_home() -> Path | None:
    for env_name in ("CCAL_TESSERACT_HOME", "TESSERACT_HOME"):
        value = os.environ.get(env_name)
        if value:
            candidate = Path(value).expanduser()
            if candidate.exists():
                return candidate

    if sys.platform.startswith("win"):
        windows_default = Path(r"C:\Program Files\Tesseract-OCR")
        if windows_default.exists():
            return windows_default

    return None


def _pyinstaller_data_arg(source: Path, destination: str) -> str:
    return f"{source}{os.pathsep}{destination}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ccal into a standalone executable with PyInstaller.")
    parser.add_argument("--onedir", action="store_true", help="Build a directory bundle instead of a one-file executable.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Output binary name.")
    parser.add_argument("--no-ocr", action="store_true", help="Skip bundling Tesseract.")
    parser.add_argument("--tesseract-home", help="Path to a local Tesseract installation to bundle.")
    args = parser.parse_args()

    pyinstaller_args: list[str] = [
        "--noconfirm",
        "--clean",
        "--name",
        args.name,
        "--console",
        "--paths",
        str(PROJECT_ROOT),
        "--runtime-hook",
        str(PROJECT_ROOT / "scripts" / "pyinstaller_tesseract_hook.py"),
        "--collect-submodules",
        "src",
        "--collect-all",
        "PIL",
        "--collect-all",
        "pytesseract",
        "--collect-all",
        "litellm",
        str(PROJECT_ROOT / "src" / "main.py"),
    ]

    if not args.onedir:
        pyinstaller_args.insert(0, "--onefile")

    if not args.no_ocr:
        tesseract_home = Path(args.tesseract_home).expanduser() if args.tesseract_home else _find_tesseract_home()
        if tesseract_home and tesseract_home.exists():
            pyinstaller_args.extend(["--add-data", _pyinstaller_data_arg(tesseract_home, "tesseract")])
            print(f"[build] Bundling Tesseract from {tesseract_home}")
        else:
            print("[build] Tesseract not found. Building without bundled OCR binaries.")

    pyinstaller_run(pyinstaller_args)


if __name__ == "__main__":
    sys.exit(main())
