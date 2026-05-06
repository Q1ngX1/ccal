from __future__ import annotations

import scripts.build_release as build_release


def test_build_release_includes_tiktoken_plugins(monkeypatch):
    captured_args = {}

    def fake_run(args):
        captured_args["args"] = list(args)

    monkeypatch.setattr(build_release, "pyinstaller_run", fake_run)
    monkeypatch.setattr(build_release, "_find_tesseract_home", lambda: None)
    monkeypatch.setattr(build_release.sys, "argv", ["build_release.py", "--no-ocr", "--name", "ccal-test"])

    build_release.main()

    args = captured_args["args"]
    assert "tiktoken" in args
    assert "tiktoken_ext" in args
    assert "litellm" in args
