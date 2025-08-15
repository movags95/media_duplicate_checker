"""Core functionality for media duplicate checker."""

from .auto_selector import AutoSelector, AutoSelectionResult, GroupFilter
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
from .similarity import SimilarityAnalyzer, SuffixDetector

__all__ = [
    "ApplicationConfig",
    "AutoSelector",
    "AutoSelectionResult",
    "DuplicateGroup",
    "DuplicateGrouper",
    "FileMetadata",
    "FilenameParser",
    "GroupFilter",
    "MediaFileScanner",
    "ParsedFilename",
    "ScanResult",
    "SimilarityAnalyzer",
    "SuffixDetector",
]
