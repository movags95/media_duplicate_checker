"""Pydantic models for media duplicate checker."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ParsedFilename(BaseModel):
    """Represents a parsed filename with extracted components."""

    original_name: str = Field(..., description="Original filename")
    base_name: str = Field(..., description="Extracted base name for matching")
    suffix: str | None = Field(None, description="Suffix after base name")
    extension: str = Field(..., description="File extension")
    pattern_type: str = Field(..., description="Type of pattern matched (GUID, IMG, etc.)")

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, v: str) -> str:
        """Ensure extension starts with a dot."""
        if not v.startswith("."):
            return f".{v}"
        return v.lower()


class FileMetadata(BaseModel):
    """Represents metadata about a media file."""

    file_path: Path = Field(..., description="Full path to the file")
    filename: str = Field(..., description="Just the filename")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    created_at: datetime = Field(..., description="File creation timestamp")
    modified_at: datetime = Field(..., description="File modification timestamp")
    parsed_filename: ParsedFilename | None = Field(None, description="Parsed filename components")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: Path) -> Path:
        """Ensure path is absolute."""
        return v.resolve()

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def extension(self) -> str:
        """File extension."""
        return self.file_path.suffix.lower()

    def __str__(self) -> str:
        return f"{self.filename} ({self.size_mb:.1f} MB)"


class DuplicateGroup(BaseModel):
    """Represents a group of potential duplicate files."""

    base_name: str = Field(..., description="Common base name for this group")
    pattern_type: str = Field(..., description="Pattern type (GUID, IMG, etc.)")
    files: list[FileMetadata] = Field(default_factory=list, description="Files in this group")
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence that these are duplicates"
    )

    @property
    def file_count(self) -> int:
        """Number of files in this group."""
        return len(self.files)

    @property
    def total_size_mb(self) -> float:
        """Total size of all files in MB."""
        return sum(file.size_mb for file in self.files)

    def add_file(self, file: FileMetadata) -> None:
        """Add a file to this duplicate group."""
        self.files.append(file)

    def get_largest_file(self) -> FileMetadata | None:
        """Get the largest file in the group."""
        if not self.files:
            return None
        return max(self.files, key=lambda f: f.size_bytes)

    def get_newest_file(self) -> FileMetadata | None:
        """Get the most recently created file in the group."""
        if not self.files:
            return None
        return max(self.files, key=lambda f: f.created_at)

    def __str__(self) -> str:
        return f"Duplicate group '{self.base_name}' ({self.file_count} files, {self.total_size_mb:.1f} MB)"


class ScanResult(BaseModel):
    """Results from a directory scan operation."""

    scan_path: Path = Field(..., description="Directory that was scanned")
    total_files_found: int = Field(..., ge=0, description="Total files discovered")
    media_files_found: int = Field(..., ge=0, description="Media files discovered")
    duplicate_groups: list[DuplicateGroup] = Field(
        default_factory=list, description="Groups of potential duplicates"
    )
    scan_duration_seconds: float = Field(..., ge=0, description="Time taken to scan")
    scan_timestamp: datetime = Field(
        default_factory=datetime.now, description="When the scan was performed"
    )

    @property
    def potential_duplicates_count(self) -> int:
        """Total number of files that are potential duplicates."""
        return sum(group.file_count for group in self.duplicate_groups if group.file_count > 1)

    @property
    def potential_space_savings_mb(self) -> float:
        """Potential space that could be saved by removing duplicates."""
        savings = 0.0
        for group in self.duplicate_groups:
            if group.file_count > 1:
                largest = group.get_largest_file()
                if largest:
                    savings += group.total_size_mb - largest.size_mb
        return savings

    def __str__(self) -> str:
        return (
            f"Scan of {self.scan_path}: {self.media_files_found} media files, "
            f"{len(self.duplicate_groups)} duplicate groups, "
            f"{self.potential_duplicates_count} potential duplicates"
        )


class ApplicationConfig(BaseModel):
    """Configuration settings for the application."""

    supported_extensions: list[str] = Field(
        default=[
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",  # Images
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".wmv",
            ".flv",
            ".webm",  # Videos
            ".heic",
            ".heif",  # Apple formats
        ],
        description="File extensions to consider as media files",
    )
    max_preview_size_mb: float = Field(
        default=50.0, gt=0, description="Maximum file size for previews"
    )
    enable_logging: bool = Field(default=True, description="Enable application logging")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Auto-selection settings
    image_similarity_threshold: float = Field(
        default=0.90, ge=0.0, le=1.0, description="Similarity threshold for auto-selecting image duplicates"
    )
    video_similarity_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Similarity threshold for auto-selecting video duplicates"
    )
    auto_selection_confidence_threshold: float = Field(
        default=0.80, ge=0.0, le=1.0, description="Minimum confidence required for auto-selection"
    )
    enable_auto_selection: bool = Field(
        default=True, description="Enable automatic selection of duplicate files"
    )

    @field_validator("supported_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str]) -> list[str]:
        """Ensure all extensions start with a dot and are lowercase."""
        return [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in v]
