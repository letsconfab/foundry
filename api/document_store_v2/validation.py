"""
Upload validation for document store.

Provides file size limits, MIME type verification (via magic bytes),
and filename sanitization to prevent security issues.
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import magic

# File size limits
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Maximum filename length (most filesystems support 255)
MAX_FILENAME_LENGTH = 255

# Allowed MIME types (verified via magic bytes, not just extension)
ALLOWED_MIME_TYPES = {
    # Text formats
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/x-markdown",
    # Structured data
    "application/json",
    "application/x-yaml",
    "text/yaml",
    "text/x-yaml",
    "application/toml",
    "text/toml",
    # PDF
    "application/pdf",
    # Office documents
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    # Images (for OCR)
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/tiff",
}

# Map common extensions to MIME types for fallback
EXTENSION_MIME_MAP = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".toml": "application/toml",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

# Characters not allowed in filenames
UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Path traversal patterns
PATH_TRAVERSAL_PATTERN = re.compile(r'(^|[\\/])\.\.($|[\\/])')


@dataclass
class ValidationResult:
    """Result of upload validation."""
    is_valid: bool
    error: Optional[str] = None
    actual_content_type: Optional[str] = None
    sanitized_filename: Optional[str] = None
    original_size: int = 0


def validate_upload(
    content: bytes,
    filename: str,
    declared_content_type: Optional[str] = None
) -> ValidationResult:
    """
    Validate a file upload.

    Checks:
    1. File size <= MAX_FILE_SIZE_BYTES
    2. MIME type is allowed (verified via magic bytes)
    3. Filename is sanitized

    Args:
        content: File content as bytes
        filename: Original filename
        declared_content_type: Content-Type header value (optional, not trusted)

    Returns:
        ValidationResult with validation status and details
    """
    original_size = len(content)

    # Check file size
    if original_size > MAX_FILE_SIZE_BYTES:
        return ValidationResult(
            is_valid=False,
            error=f"File size ({original_size / 1024 / 1024:.1f}MB) exceeds maximum ({MAX_FILE_SIZE_MB}MB)",
            original_size=original_size,
        )

    # Check for empty files
    if original_size == 0:
        return ValidationResult(
            is_valid=False,
            error="File is empty",
            original_size=0,
        )

    # Detect actual MIME type via magic bytes
    actual_content_type = detect_mime_type(content, filename)

    # Check if MIME type is allowed
    if actual_content_type not in ALLOWED_MIME_TYPES:
        return ValidationResult(
            is_valid=False,
            error=f"File type '{actual_content_type}' is not allowed",
            actual_content_type=actual_content_type,
            original_size=original_size,
        )

    # Sanitize filename
    sanitized = sanitize_filename(filename)
    if not sanitized:
        return ValidationResult(
            is_valid=False,
            error="Invalid filename",
            actual_content_type=actual_content_type,
            original_size=original_size,
        )

    return ValidationResult(
        is_valid=True,
        actual_content_type=actual_content_type,
        sanitized_filename=sanitized,
        original_size=original_size,
    )


def detect_mime_type(content: bytes, filename: str) -> str:
    """
    Detect MIME type using magic bytes, with extension fallback.

    Args:
        content: File content
        filename: Original filename (for extension fallback)

    Returns:
        Detected MIME type string
    """
    # Try magic bytes detection first
    try:
        mime = magic.Magic(mime=True)
        detected = mime.from_buffer(content)

        # Magic sometimes returns generic types for text files
        # Use extension to refine if detected as text/plain
        if detected == "text/plain":
            ext = os.path.splitext(filename.lower())[1]
            if ext in EXTENSION_MIME_MAP:
                return EXTENSION_MIME_MAP[ext]

        return detected
    except Exception:
        # Fallback to extension-based detection
        ext = os.path.splitext(filename.lower())[1]
        return EXTENSION_MIME_MAP.get(ext, "application/octet-stream")


def sanitize_filename(filename: str) -> Optional[str]:
    """
    Sanitize filename for safe storage.

    Removes:
    - Path components (directory traversal)
    - Null bytes
    - Control characters
    - Unsafe characters for filesystems

    Args:
        filename: Original filename

    Returns:
        Sanitized filename, or None if invalid
    """
    if not filename:
        return None

    # Normalize unicode
    filename = unicodedata.normalize("NFC", filename)

    # Remove any path components (keep only the basename)
    filename = os.path.basename(filename)

    # Check for path traversal attempts
    if PATH_TRAVERSAL_PATTERN.search(filename):
        return None

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove unsafe characters
    filename = UNSAFE_FILENAME_CHARS.sub("_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Ensure filename is not empty after sanitization
    if not filename:
        return None

    # Truncate to max length while preserving extension
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        max_name_len = MAX_FILENAME_LENGTH - len(ext)
        if max_name_len > 0:
            filename = name[:max_name_len] + ext
        else:
            filename = filename[:MAX_FILENAME_LENGTH]

    return filename


def get_accepted_formats() -> list[str]:
    """
    Get list of accepted file formats for UI display.

    Returns:
        List of file extensions without dots (e.g., ["pdf", "docx", "txt"])
    """
    return [ext.lstrip(".") for ext in EXTENSION_MIME_MAP.keys()]
