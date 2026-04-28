# Building Standalone Releases

`ccal` can be packaged with PyInstaller into standalone Windows, Linux, and macOS builds.

## Recommended workflow

1. Build on the target platform. PyInstaller does not replace native platform packaging, especially for macOS notarization.
2. Use the repo helper script:

```bash
uv run python scripts/build_release.py
```

3. If your local Tesseract install is not auto-detected, pass it explicitly:

```bash
uv run python scripts/build_release.py --tesseract-home "C:\Program Files\Tesseract-OCR"
```

## OCR packaging

- Python dependencies: `pytesseract` and `Pillow`
- Native binary: the `tesseract` executable
- Language data: the `tessdata` directory, including any `.traineddata` files you need

The build script copies the Tesseract installation directory into the frozen app and the runtime hook points `pytesseract` at the bundled binary.

If you do not want OCR bundled, use:

```bash
uv run python scripts/build_release.py --no-ocr
```

## Notes by platform

- Windows: bundle `C:\Program Files\Tesseract-OCR` or another local install directory.
- Linux: build on Linux and bundle the system Tesseract install or a portable Tesseract tree.
- macOS: build on macOS, then sign and notarize the resulting app or binary if you distribute it publicly.

## GitHub Releases

The repository includes a GitHub Actions workflow that builds release assets on tag pushes (`v*`) and uploads them to a GitHub Release.

- Windows builds include bundled OCR when Tesseract is available on the runner.
- Linux and macOS builds currently publish the core CLI without bundled OCR binaries.
