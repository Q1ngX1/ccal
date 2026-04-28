import os
from pathlib import Path
from unittest.mock import patch

from src.input.tesseract_runtime import (
    configure_tesseract_runtime,
    find_tessdata_prefix,
    find_tesseract_cmd,
    find_tesseract_home,
)


def test_find_tesseract_home_prefers_env(tmp_path, monkeypatch):
    home = tmp_path / "Tesseract-OCR"
    home.mkdir()
    monkeypatch.setenv("CCAL_TESSERACT_HOME", str(home))
    assert find_tesseract_home() == home


def test_find_tesseract_cmd_uses_env_cmd(tmp_path, monkeypatch):
    cmd = tmp_path / "tesseract.exe"
    cmd.write_text("fake")
    monkeypatch.setenv("CCAL_TESSERACT_CMD", str(cmd))
    assert find_tesseract_cmd() == cmd


def test_find_tessdata_prefix_from_bundle(tmp_path, monkeypatch):
    bundle_home = tmp_path / "bundle" / "tesseract"
    tessdata = bundle_home / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_text("fake")
    cmd = bundle_home / "tesseract.exe"
    cmd.write_text("fake")
    monkeypatch.setenv("CCAL_TESSERACT_HOME", str(bundle_home))
    assert find_tessdata_prefix(bundle_home, cmd) == bundle_home


def test_configure_tesseract_runtime_sets_pytesseract_path(tmp_path, monkeypatch):
    bundle_home = tmp_path / "bundle" / "tesseract"
    tessdata = bundle_home / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_text("fake")
    cmd = bundle_home / "tesseract.exe"
    cmd.write_text("fake")

    monkeypatch.setenv("CCAL_TESSERACT_HOME", str(bundle_home))
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)

    with patch("src.input.tesseract_runtime.find_tesseract_home", return_value=bundle_home), patch(
        "src.input.tesseract_runtime.find_tesseract_cmd", return_value=cmd
    ):
        configure_tesseract_runtime()

    import pytesseract

    assert Path(pytesseract.pytesseract.tesseract_cmd) == cmd
    assert Path(os.environ["TESSDATA_PREFIX"]) == bundle_home
