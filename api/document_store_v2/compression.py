"""
Compression service using zstd.

zstd provides excellent compression ratio and speed balance.
Default compression level 3 is optimized for general use.
"""

import zstandard as zstd

# Default compression level (1-22, higher = better ratio but slower)
# Level 3 provides good balance for document content
DEFAULT_COMPRESSION_LEVEL = 3


def compress(data: bytes, level: int = DEFAULT_COMPRESSION_LEVEL) -> bytes:
    """
    Compress data using zstd.

    Args:
        data: Raw bytes to compress
        level: Compression level (1-22), default 3

    Returns:
        Compressed bytes
    """
    compressor = zstd.ZstdCompressor(level=level)
    return compressor.compress(data)


def decompress(data: bytes) -> bytes:
    """
    Decompress zstd-compressed data.

    Args:
        data: Compressed bytes

    Returns:
        Original uncompressed bytes
    """
    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(data)


def get_compression_ratio(original_size: int, compressed_size: int) -> float:
    """
    Calculate compression ratio.

    Args:
        original_size: Size before compression
        compressed_size: Size after compression

    Returns:
        Ratio as float (e.g., 0.45 means compressed to 45% of original)
    """
    if original_size == 0:
        return 1.0
    return compressed_size / original_size
