from pathlib import Path

from src.input.tesseract_runtime import configure_tesseract_runtime

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

_OCR_INSTALL_HINT = (
    "OCR dependencies not installed. "
    "Install them with: pip install ccal[ocr]"
)


def _check_ocr_deps() -> None:
    """Raise ImportError if OCR dependencies are missing."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        raise ImportError(_OCR_INSTALL_HINT)


def extract_text(image_path: str, language: str | None = None) -> str:
    """Extract text from an image file using pytesseract OCR."""
    configure_tesseract_runtime()
    _check_ocr_deps()
    import pytesseract
    from PIL import Image

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    try:
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang=language) if language else pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract executable not found. Install Tesseract or set CCAL_TESSERACT_HOME/CCAL_TESSERACT_CMD."
        ) from exc
    return text.strip()


def is_image_file(path_str: str) -> bool:
    """Check if the given path looks like a supported image file."""
    path = Path(path_str)
    return path.exists() and path.suffix.lower() in SUPPORTED_EXTENSIONS
