"""Tests for src/input/ocr.py — image text extraction."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.input.ocr import extract_text, is_image_file, SUPPORTED_EXTENSIONS, _check_ocr_deps


class TestIsImageFile:
    def test_png_exists(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        assert is_image_file(str(img)) is True

    def test_jpg_exists(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"fake")
        assert is_image_file(str(img)) is True

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"fake")
        assert is_image_file(str(f)) is False

    def test_nonexistent_file(self):
        assert is_image_file("/nonexistent/file.png") is False

    def test_text_string(self):
        assert is_image_file("Meeting tomorrow at 3pm") is False


class TestExtractText:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            extract_text("/nonexistent/image.png")

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"data")
        with pytest.raises(ValueError, match="Unsupported image format"):
            extract_text(str(f))

    def test_successful_extraction(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png data")

        mock_image = MagicMock()
        with (
            patch("PIL.Image.open", return_value=mock_image),
            patch("pytesseract.image_to_string", return_value="  Meeting at 3pm  "),
        ):
            result = extract_text(str(img))
        assert result == "Meeting at 3pm"

    def test_extraction_with_language(self, tmp_path):
        img = tmp_path / "chinese.png"
        img.write_bytes(b"fake")

        mock_image = MagicMock()
        with (
            patch("PIL.Image.open", return_value=mock_image),
            patch("pytesseract.image_to_string", return_value="会议") as mock_ocr,
        ):
            result = extract_text(str(img), language="chi_sim")
            mock_ocr.assert_called_once_with(mock_image, lang="chi_sim")
        assert result == "会议"

    def test_supported_extensions_complete(self):
        expected = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
        assert SUPPORTED_EXTENSIONS == expected


class TestOcrDepsCheck:
    def test_missing_deps_raises_import_error(self):
        with patch.dict("sys.modules", {"pytesseract": None}):
            with pytest.raises(ImportError, match="pip install ccal\\[ocr\\]"):
                _check_ocr_deps()

    def test_deps_present_no_error(self):
        # Should not raise when deps are installed
        _check_ocr_deps()
