"""PyInstaller runtime hook for bundled Tesseract binaries."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _set_bundle_env() -> None:
    frozen_root = Path(getattr(sys, "_MEIPASS", "")).resolve() if getattr(sys, "frozen", False) else None
    if not frozen_root:
        return

    bundled_tesseract = frozen_root / "tesseract"
    if bundled_tesseract.exists():
        os.environ.setdefault("CCAL_TESSERACT_HOME", str(bundled_tesseract))

        # Let bundled POSIX binaries run if they were shipped as data.
        if os.name != "nt":
            tesseract_bin = bundled_tesseract / "tesseract"
            if tesseract_bin.exists():
                try:
                    tesseract_bin.chmod(0o755)
                except OSError:
                    pass


_set_bundle_env()
