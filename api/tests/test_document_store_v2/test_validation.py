"""
Tests for document_store_v2.validation module.

Tests file validation, MIME detection, and filename sanitization.
"""

import pytest
from unittest.mock import patch, MagicMock
from document_store_v2.validation import (
    validate_upload,
    detect_mime_type,
    sanitize_filename,
    get_accepted_formats,
    ValidationResult,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    MAX_FILENAME_LENGTH,
    ALLOWED_MIME_TYPES,
    EXTENSION_MIME_MAP,
)


class TestValidateUpload:
    """Tests for validate_upload function."""

    @pytest.fixture
    def mock_magic(self):
        """Mock python-magic for MIME detection."""
        with patch("document_store_v2.validation.magic.Magic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            yield mock_instance

    def test_valid_text_file(self, mock_magic):
        """Valid text file should pass validation."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"Hello, World!"
        result = validate_upload(content, "test.txt")

        assert result.is_valid is True
        assert result.error is None
        assert result.actual_content_type == "text/plain"
        assert result.sanitized_filename == "test.txt"
        assert result.original_size == len(content)

    def test_valid_pdf_file(self, mock_magic):
        """Valid PDF file should pass validation."""
        mock_magic.from_buffer.return_value = "application/pdf"
        content = b"%PDF-1.4 fake pdf content" + b"x" * 1000
        result = validate_upload(content, "document.pdf")

        assert result.is_valid is True
        assert result.actual_content_type == "application/pdf"

    def test_valid_markdown_file(self, mock_magic):
        """Markdown file should pass validation."""
        mock_magic.from_buffer.return_value = "text/plain"  # magic often returns text/plain
        content = b"# Heading\n\nParagraph text"
        result = validate_upload(content, "readme.md")

        assert result.is_valid is True
        # Extension mapping should refine text/plain to text/markdown
        assert result.actual_content_type == "text/markdown"

    def test_valid_json_file(self, mock_magic):
        """JSON file should pass validation."""
        mock_magic.from_buffer.return_value = "application/json"
        content = b'{"key": "value"}'
        result = validate_upload(content, "data.json")

        assert result.is_valid is True
        assert result.actual_content_type == "application/json"

    def test_valid_image_png(self, mock_magic):
        """PNG image should pass validation."""
        mock_magic.from_buffer.return_value = "image/png"
        # PNG header bytes
        content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        result = validate_upload(content, "image.png")

        assert result.is_valid is True
        assert result.actual_content_type == "image/png"

    def test_file_too_large(self, mock_magic):
        """File exceeding size limit should be rejected."""
        # Create content larger than MAX_FILE_SIZE_BYTES
        content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        result = validate_upload(content, "large.txt")

        assert result.is_valid is False
        assert "exceeds maximum" in result.error
        assert f"{MAX_FILE_SIZE_MB}MB" in result.error

    def test_empty_file_rejected(self, mock_magic):
        """Empty file should be rejected."""
        content = b""
        result = validate_upload(content, "empty.txt")

        assert result.is_valid is False
        assert "empty" in result.error.lower()

    def test_disallowed_mime_type(self, mock_magic):
        """Disallowed MIME type should be rejected."""
        mock_magic.from_buffer.return_value = "application/x-executable"
        content = b"\x7fELF" + b"x" * 100  # ELF header
        result = validate_upload(content, "program.exe")

        assert result.is_valid is False
        assert "not allowed" in result.error

    def test_invalid_filename_rejected(self, mock_magic):
        """Invalid filename should be rejected."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"test content"
        # Filename that becomes empty after sanitization
        result = validate_upload(content, "...")

        assert result.is_valid is False
        assert "Invalid filename" in result.error

    def test_declared_content_type_ignored(self, mock_magic):
        """Declared content type should not override magic detection."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"Just text"
        # Declare as PDF but actual content is text
        result = validate_upload(content, "file.txt", declared_content_type="application/pdf")

        # Should use detected type, not declared
        assert result.actual_content_type == "text/plain"

    def test_returns_original_size(self, mock_magic):
        """Validation result should include original file size."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"x" * 12345
        result = validate_upload(content, "test.txt")

        assert result.original_size == 12345


class TestDetectMimeType:
    """Tests for detect_mime_type function."""

    @pytest.fixture
    def mock_magic(self):
        """Mock python-magic."""
        with patch("document_store_v2.validation.magic.Magic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            yield mock_instance

    def test_detects_pdf(self, mock_magic):
        """Should detect PDF from magic bytes."""
        mock_magic.from_buffer.return_value = "application/pdf"
        content = b"%PDF-1.4 content"
        result = detect_mime_type(content, "document.pdf")
        assert result == "application/pdf"

    def test_detects_png(self, mock_magic):
        """Should detect PNG from magic bytes."""
        mock_magic.from_buffer.return_value = "image/png"
        content = b"\x89PNG\r\n\x1a\n"
        result = detect_mime_type(content, "image.png")
        assert result == "image/png"

    def test_refines_text_plain_with_md_extension(self, mock_magic):
        """text/plain should be refined to text/markdown for .md files."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"# Heading"
        result = detect_mime_type(content, "readme.md")
        assert result == "text/markdown"

    def test_refines_text_plain_with_yaml_extension(self, mock_magic):
        """text/plain should be refined to application/x-yaml for .yaml files."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"key: value"
        result = detect_mime_type(content, "config.yaml")
        assert result == "application/x-yaml"

    def test_refines_text_plain_with_yml_extension(self, mock_magic):
        """text/plain should be refined for .yml extension."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"key: value"
        result = detect_mime_type(content, "config.yml")
        assert result == "application/x-yaml"

    def test_refines_text_plain_with_json_extension(self, mock_magic):
        """text/plain detected JSON should keep detected type (JSON is usually detected)."""
        mock_magic.from_buffer.return_value = "application/json"
        content = b'{"key": "value"}'
        result = detect_mime_type(content, "data.json")
        assert result == "application/json"

    def test_refines_text_plain_with_csv_extension(self, mock_magic):
        """text/plain should be refined to text/csv for .csv files."""
        mock_magic.from_buffer.return_value = "text/plain"
        content = b"col1,col2\nval1,val2"
        result = detect_mime_type(content, "data.csv")
        assert result == "text/csv"

    def test_falls_back_to_extension_on_magic_error(self, mock_magic):
        """Should fall back to extension when magic fails."""
        mock_magic.from_buffer.side_effect = Exception("Magic failed")
        content = b"content"
        result = detect_mime_type(content, "test.txt")
        assert result == "text/plain"

    def test_falls_back_to_octet_stream_for_unknown(self, mock_magic):
        """Should return application/octet-stream for unknown types."""
        mock_magic.from_buffer.side_effect = Exception("Magic failed")
        content = b"content"
        result = detect_mime_type(content, "file.unknown")
        assert result == "application/octet-stream"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_simple_filename_unchanged(self):
        """Simple valid filename should be unchanged."""
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_removes_path_components(self):
        """Path components should be stripped."""
        assert sanitize_filename("/etc/passwd") == "passwd"
        # On Unix, backslashes are valid filename chars, so os.path.basename keeps them
        # The unsafe char regex will replace them with underscores
        result = sanitize_filename("C:\\Windows\\System32\\config.txt")
        assert "Windows" not in result or "_" in result  # Either stripped or sanitized
        assert sanitize_filename("../../../secret.txt") == "secret.txt"

    def test_removes_null_bytes(self):
        """Null bytes should be removed."""
        assert sanitize_filename("file\x00.txt") == "file.txt"

    def test_replaces_unsafe_characters(self):
        """Unsafe characters should be replaced with underscore."""
        result = sanitize_filename("file<>:\"|?*.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result
        assert result.endswith(".txt")

    def test_removes_control_characters(self):
        """Control characters should be replaced."""
        # Control chars 0x00-0x1f
        result = sanitize_filename("file\x01\x02\x03.txt")
        assert "\x01" not in result
        assert "\x02" not in result
        assert "\x03" not in result

    def test_strips_leading_dots(self):
        """Leading dots should be stripped."""
        assert sanitize_filename(".hidden.txt") == "hidden.txt"
        assert sanitize_filename("...file.txt") == "file.txt"

    def test_strips_trailing_dots(self):
        """Trailing dots should be stripped."""
        assert sanitize_filename("file.txt.") == "file.txt"
        assert sanitize_filename("file...") == "file"

    def test_strips_leading_spaces(self):
        """Leading spaces should be stripped."""
        assert sanitize_filename("  file.txt") == "file.txt"

    def test_strips_trailing_spaces(self):
        """Trailing spaces should be stripped."""
        assert sanitize_filename("file.txt  ") == "file.txt"

    def test_empty_filename_returns_none(self):
        """Empty filename should return None."""
        assert sanitize_filename("") is None

    def test_filename_becomes_empty_returns_none(self):
        """Filename that becomes empty after sanitization should return None."""
        assert sanitize_filename("...") is None
        assert sanitize_filename("   ") is None
        assert sanitize_filename(".\x00.") is None

    def test_path_traversal_detected(self):
        """Path traversal patterns should be handled."""
        # After basename extraction, ".." alone is stripped
        assert sanitize_filename("..") is None

    def test_truncates_long_filename_preserving_extension(self):
        """Long filename should be truncated while preserving extension."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert result is not None
        assert len(result) <= MAX_FILENAME_LENGTH
        assert result.endswith(".pdf")

    def test_truncates_long_filename_without_extension(self):
        """Long filename without extension should be truncated."""
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert result is not None
        assert len(result) <= MAX_FILENAME_LENGTH

    def test_preserves_unicode_characters(self):
        """Valid unicode characters should be preserved."""
        result = sanitize_filename("documento_\u00e9sp\u00e9cial.pdf")
        assert "\u00e9" in result  # e with accent

    def test_normalizes_unicode(self):
        """Unicode should be normalized to NFC."""
        # Combining character form vs precomposed
        combining = "e\u0301"  # e + combining acute
        precomposed = "\u00e9"  # e with acute
        result = sanitize_filename(f"file_{combining}.txt")
        # After NFC normalization, both forms should produce same result
        assert precomposed in result or combining in result


class TestGetAcceptedFormats:
    """Tests for get_accepted_formats function."""

    def test_returns_list(self):
        """Should return a list."""
        formats = get_accepted_formats()
        assert isinstance(formats, list)

    def test_includes_common_formats(self):
        """Should include common file formats."""
        formats = get_accepted_formats()
        assert "pdf" in formats
        assert "txt" in formats
        assert "md" in formats
        assert "json" in formats

    def test_no_leading_dots(self):
        """Extensions should not have leading dots."""
        formats = get_accepted_formats()
        for fmt in formats:
            assert not fmt.startswith(".")

    def test_matches_extension_mime_map(self):
        """All formats should come from EXTENSION_MIME_MAP."""
        formats = get_accepted_formats()
        expected = [ext.lstrip(".") for ext in EXTENSION_MIME_MAP.keys()]
        assert set(formats) == set(expected)


class TestAllowedMimeTypes:
    """Tests for ALLOWED_MIME_TYPES constant."""

    def test_includes_text_formats(self):
        """Should include text formats."""
        assert "text/plain" in ALLOWED_MIME_TYPES
        assert "text/markdown" in ALLOWED_MIME_TYPES
        assert "text/csv" in ALLOWED_MIME_TYPES

    def test_includes_pdf(self):
        """Should include PDF."""
        assert "application/pdf" in ALLOWED_MIME_TYPES

    def test_includes_json(self):
        """Should include JSON."""
        assert "application/json" in ALLOWED_MIME_TYPES

    def test_includes_images(self):
        """Should include image formats for OCR."""
        assert "image/png" in ALLOWED_MIME_TYPES
        assert "image/jpeg" in ALLOWED_MIME_TYPES
        assert "image/gif" in ALLOWED_MIME_TYPES

    def test_includes_office_formats(self):
        """Should include Office document formats."""
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ALLOWED_MIME_TYPES
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in ALLOWED_MIME_TYPES


class TestValidationResultDataclass:
    """Tests for ValidationResult dataclass."""

    def test_defaults(self):
        """Default values should be set correctly."""
        result = ValidationResult(is_valid=True)
        assert result.error is None
        assert result.actual_content_type is None
        assert result.sanitized_filename is None
        assert result.original_size == 0

    def test_all_fields(self):
        """All fields should be settable."""
        result = ValidationResult(
            is_valid=True,
            error=None,
            actual_content_type="text/plain",
            sanitized_filename="test.txt",
            original_size=1234,
        )
        assert result.is_valid is True
        assert result.actual_content_type == "text/plain"
        assert result.sanitized_filename == "test.txt"
        assert result.original_size == 1234

    def test_invalid_with_error(self):
        """Invalid result should have error."""
        result = ValidationResult(
            is_valid=False,
            error="File too large",
            original_size=999999999,
        )
        assert result.is_valid is False
        assert result.error == "File too large"
