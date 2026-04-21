"""
Tests for document_store_v2.compression module.

Tests zstd compression/decompression and ratio calculation.
"""

import pytest
from document_store_v2.compression import (
    compress,
    decompress,
    get_compression_ratio,
    DEFAULT_COMPRESSION_LEVEL,
)


class TestCompress:
    """Tests for compress function."""

    def test_compress_returns_bytes(self):
        """Compress should return bytes."""
        data = b"Hello, World!"
        result = compress(data)
        assert isinstance(result, bytes)

    def test_compress_reduces_size_for_compressible_data(self):
        """Compressible data should be smaller after compression."""
        # Highly repetitive data compresses well
        data = b"A" * 10000
        compressed = compress(data)
        assert len(compressed) < len(data)

    def test_compress_with_different_levels(self):
        """Different compression levels should work."""
        data = b"Test data " * 100

        level_1 = compress(data, level=1)
        level_10 = compress(data, level=10)

        # Both should be valid compressed data
        assert decompress(level_1) == data
        assert decompress(level_10) == data

        # Higher level should give better (or equal) compression
        assert len(level_10) <= len(level_1)

    def test_compress_default_level(self):
        """Default compression level should be applied."""
        assert DEFAULT_COMPRESSION_LEVEL == 3

    def test_compress_empty_data(self):
        """Empty data should compress without error."""
        data = b""
        compressed = compress(data)
        assert isinstance(compressed, bytes)
        # Empty data still produces zstd header
        assert len(compressed) > 0

    def test_compress_single_byte(self):
        """Single byte should compress without error."""
        data = b"X"
        compressed = compress(data)
        assert decompress(compressed) == data

    def test_compress_binary_data(self):
        """Binary data (non-UTF8) should compress correctly."""
        data = bytes(range(256)) * 100
        compressed = compress(data)
        assert decompress(compressed) == data

    def test_compress_large_data(self):
        """Large data should compress correctly."""
        # 1MB of compressible data
        data = b"The quick brown fox jumps over the lazy dog. " * 25000
        compressed = compress(data)

        # Should compress significantly
        assert len(compressed) < len(data) / 2
        assert decompress(compressed) == data


class TestDecompress:
    """Tests for decompress function."""

    def test_decompress_returns_bytes(self):
        """Decompress should return bytes."""
        data = b"Test data"
        compressed = compress(data)
        result = decompress(compressed)
        assert isinstance(result, bytes)

    def test_decompress_round_trip(self):
        """Data should be unchanged after compress -> decompress."""
        original = b"Hello, World! This is a test of compression."
        compressed = compress(original)
        decompressed = decompress(compressed)
        assert decompressed == original

    def test_decompress_empty_data(self):
        """Decompressing empty data compressed should return empty bytes."""
        original = b""
        compressed = compress(original)
        decompressed = decompress(compressed)
        assert decompressed == b""

    def test_decompress_invalid_data_raises(self):
        """Decompressing invalid data should raise an exception."""
        invalid_data = b"This is not valid zstd compressed data"
        with pytest.raises(Exception):  # zstd.ZstdError
            decompress(invalid_data)

    def test_decompress_truncated_data_raises(self):
        """Decompressing truncated compressed data should raise an exception."""
        data = b"Hello" * 1000
        compressed = compress(data)
        truncated = compressed[:10]
        with pytest.raises(Exception):
            decompress(truncated)


class TestGetCompressionRatio:
    """Tests for get_compression_ratio function."""

    def test_ratio_of_equal_sizes(self):
        """Equal sizes should return 1.0."""
        ratio = get_compression_ratio(1000, 1000)
        assert ratio == 1.0

    def test_ratio_of_half_compression(self):
        """Compressing to half size should return 0.5."""
        ratio = get_compression_ratio(1000, 500)
        assert ratio == 0.5

    def test_ratio_of_quarter_compression(self):
        """Compressing to quarter size should return 0.25."""
        ratio = get_compression_ratio(1000, 250)
        assert ratio == 0.25

    def test_ratio_with_zero_original_size(self):
        """Zero original size should return 1.0 (avoid division by zero)."""
        ratio = get_compression_ratio(0, 0)
        assert ratio == 1.0

    def test_ratio_with_expansion(self):
        """If compressed is larger, ratio > 1.0."""
        # This can happen with incompressible data + overhead
        ratio = get_compression_ratio(100, 150)
        assert ratio == 1.5

    def test_ratio_returns_float(self):
        """Ratio should always be a float."""
        ratio = get_compression_ratio(1000, 333)
        assert isinstance(ratio, float)
        assert pytest.approx(ratio, 0.001) == 0.333


class TestRoundTripVariousContent:
    """Integration tests for compress/decompress with various content types."""

    def test_json_content(self):
        """JSON content should round-trip correctly."""
        import json
        data = json.dumps({"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}).encode()
        assert decompress(compress(data)) == data

    def test_markdown_content(self):
        """Markdown content should round-trip correctly."""
        data = b"# Heading\n\n**Bold** and *italic* text.\n\n- List item 1\n- List item 2"
        assert decompress(compress(data)) == data

    def test_pdf_like_binary(self):
        """Binary data resembling PDF should round-trip correctly."""
        # PDF magic bytes + some content
        data = b"%PDF-1.4\n" + bytes(range(256)) * 50
        assert decompress(compress(data)) == data

    def test_unicode_utf8_content(self):
        """UTF-8 encoded unicode content should round-trip correctly."""
        text = "Hello World! Emoji: \U0001F600 CJK: \u4E2D\u6587 Cyrillic: \u041F\u0440\u0438\u0432\u0435\u0442"
        data = text.encode("utf-8")
        assert decompress(compress(data)) == data
