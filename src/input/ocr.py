from pathlib import Path

import pytesseract
from PIL import Image

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def extract_text(image_path: str, language: str | None = None) -> str:
    """Extract text from an image file using pytesseract OCR."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang=language) if language else pytesseract.image_to_string(img)
    return text.strip()


def is_image_file(path_str: str) -> bool:
    """Check if the given path looks like a supported image file."""
    path = Path(path_str)
    return path.exists() and path.suffix.lower() in SUPPORTED_EXTENSIONS
