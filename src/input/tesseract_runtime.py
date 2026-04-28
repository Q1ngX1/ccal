from __future__ import annotations

import os
import sys
from pathlib import Path
from shutil import which


def configure_tesseract_runtime() -> None:
    """Point pytesseract at a usable Tesseract binary and tessdata directory."""
    tesseract_home = find_tesseract_home()
    tesseract_cmd = find_tesseract_cmd(tesseract_home)
    if tesseract_cmd is None:
        return

    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)

    tessdata_prefix = find_tessdata_prefix(tesseract_home, tesseract_cmd)
    if tessdata_prefix and not os.environ.get("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(tessdata_prefix)


def find_tesseract_home() -> Path | None:
    """Find the root directory that contains a Tesseract installation."""
    for candidate in _home_candidates():
        if candidate and candidate.exists():
            return candidate
    return None


def find_tesseract_cmd(home: Path | None = None) -> Path | None:
    """Find the Tesseract executable."""
    env_cmd = os.environ.get("CCAL_TESSERACT_CMD") or os.environ.get("TESSERACT_CMD")
    if env_cmd:
        candidate = Path(env_cmd).expanduser()
        if candidate.exists():
            return candidate

    if home:
        for candidate in _candidate_executables(home):
            if candidate.exists():
                return candidate

    system_cmd = which("tesseract")
    if system_cmd:
        return Path(system_cmd)

    return None


def find_tessdata_prefix(home: Path | None = None, tesseract_cmd: Path | None = None) -> Path | None:
    """Find a directory suitable for TESSDATA_PREFIX."""
    roots = []
    if home:
        roots.append(home)

    if tesseract_cmd:
        roots.append(tesseract_cmd.parent)
        roots.append(tesseract_cmd.parent.parent)

    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", "")).resolve()
        roots.append(meipass)
        roots.append(meipass / "tesseract")

    for root in roots:
        if not root:
            continue
        for prefix in _candidate_tessdata_prefixes(root):
            if prefix is not None and _has_tessdata(prefix):
                return prefix
    return None


def _home_candidates() -> list[Path]:
    candidates: list[Path] = []

    for env_name in ("CCAL_TESSERACT_HOME", "TESSERACT_HOME"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value).expanduser())

    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", "")).resolve()
        candidates.extend(
            [
                meipass / "tesseract",
                meipass,
                Path(sys.executable).resolve().parent / "tesseract",
                Path(sys.executable).resolve().parent,
            ]
        )

    candidates.extend(
        [
            Path(r"C:\Program Files\Tesseract-OCR"),
            Path("/usr/bin"),
            Path("/usr/local/bin"),
            Path("/opt/homebrew/bin"),
        ]
    )
    return candidates


def _candidate_executables(home: Path) -> list[Path]:
    names = ["tesseract.exe", "tesseract"] if os.name == "nt" else ["tesseract", "tesseract.exe"]
    paths = [
        home / name
        for name in names
    ]
    paths.extend(home / "bin" / name for name in names)
    paths.extend(home / "tesseract" / name for name in names)
    return paths


def _candidate_tessdata_prefixes(root: Path) -> list[Path]:
    return [
        root,
        root / "share",
        root / "share" / "tesseract-ocr" / "5",
    ]


def _has_tessdata(prefix: Path) -> bool:
    return (prefix / "tessdata").exists()
