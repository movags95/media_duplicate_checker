"""Core functionality for media duplicate checker."""

from .grouper import DuplicateGrouper
from .models import (
    ApplicationConfig,
    DuplicateGroup,
    FileMetadata,
    ParsedFilename,
    ScanResult,
)
from .parser import FilenameParser
from .scanner import MediaFileScanner

__all__ = [
    "ApplicationConfig",
    "DuplicateGroup",
    "DuplicateGrouper",
    "FileMetadata",
    "FilenameParser",
    "MediaFileScanner",
    "ParsedFilename",
    "ScanResult",
]
