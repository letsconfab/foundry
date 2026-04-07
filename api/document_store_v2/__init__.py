"""
Document Store V2 - Versioned document storage with compression and encryption.

This module provides a PostgreSQL-native document store with:
- Version history (all versions retained)
- zstd compression
- AES-256-GCM encryption (Phase 2)
- File validation and sanitization
"""

from .compression import compress, decompress
from .validation import validate_upload, sanitize_filename, ValidationResult, get_accepted_formats
from .service import DocumentServiceV2

__all__ = [
    "compress",
    "decompress",
    "validate_upload",
    "sanitize_filename",
    "ValidationResult",
    "get_accepted_formats",
    "DocumentServiceV2",
]
