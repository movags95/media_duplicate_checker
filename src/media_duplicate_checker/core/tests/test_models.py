"""Tests for Pydantic models."""

from datetime import datetime
from pathlib import Path

from ..models import (
    ApplicationConfig,
    DuplicateGroup,
    FileMetadata,
    ParsedFilename,
    ScanResult,
)


class TestParsedFilename:
    """Test cases for ParsedFilename model."""

    def test_create_parsed_filename(self) -> None:
        """Test creating a ParsedFilename object."""
        parsed = ParsedFilename(
            original_name="IMG_1234-56788.HEIC",
            base_name="img_1234",
            suffix="56788",
            extension=".HEIC",
            pattern_type="IMG",
        )

        assert parsed.original_name == "IMG_1234-56788.HEIC"
        assert parsed.base_name == "img_1234"
        assert parsed.suffix == "56788"
        assert parsed.extension == ".heic"
        assert parsed.pattern_type == "IMG"

    def test_extension_validation_adds_dot(self) -> None:
        """Test that extension validation adds dot if missing."""
        parsed = ParsedFilename(
            original_name="test.jpg",
            base_name="test",
            extension="jpg",  # Missing dot
            pattern_type="GENERIC",
        )

        assert parsed.extension == ".jpg"

    def test_extension_validation_lowercase(self) -> None:
        """Test that extension validation converts to lowercase."""
        parsed = ParsedFilename(
            original_name="test.JPG", base_name="test", extension=".JPG", pattern_type="GENERIC"
        )

        assert parsed.extension == ".jpg"


class TestFileMetadata:
    """Test cases for FileMetadata model."""

    def test_create_file_metadata(self) -> None:
        """Test creating a FileMetadata object."""
        test_path = Path("/test/path/IMG_1234.HEIC")
        created = datetime(2023, 1, 1, 12, 0, 0)
        modified = datetime(2023, 1, 1, 12, 30, 0)

        metadata = FileMetadata(
            file_path=test_path,
            filename="IMG_1234.HEIC",
            size_bytes=1048576,  # 1 MB
            created_at=created,
            modified_at=modified,
        )

        assert metadata.file_path == test_path.resolve()
        assert metadata.filename == "IMG_1234.HEIC"
        assert metadata.size_bytes == 1048576
        assert metadata.created_at == created
        assert metadata.modified_at == modified

    def test_size_mb_property(self) -> None:
        """Test size_mb property calculation."""
        metadata = FileMetadata(
            file_path=Path("/test/file.jpg"),
            filename="file.jpg",
            size_bytes=2097152,  # 2 MB
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )

        assert metadata.size_mb == 2.0

    def test_extension_property(self) -> None:
        """Test extension property."""
        metadata = FileMetadata(
            file_path=Path("/test/file.JPEG"),
            filename="file.JPEG",
            size_bytes=1000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )

        assert metadata.extension == ".jpeg"

    def test_str_representation(self) -> None:
        """Test string representation."""
        metadata = FileMetadata(
            file_path=Path("/test/file.jpg"),
            filename="file.jpg",
            size_bytes=1048576,  # 1 MB
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )

        assert str(metadata) == "file.jpg (1.0 MB)"

    def test_file_path_validation(self) -> None:
        """Test that file paths are resolved to absolute paths."""
        relative_path = Path("relative/path/file.jpg")
        metadata = FileMetadata(
            file_path=relative_path,
            filename="file.jpg",
            size_bytes=1000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )

        # Should be resolved to absolute path
        assert metadata.file_path.is_absolute()


class TestDuplicateGroup:
    """Test cases for DuplicateGroup model."""

    def test_create_duplicate_group(self) -> None:
        """Test creating a DuplicateGroup object."""
        group = DuplicateGroup(base_name="img_1234", pattern_type="IMG", confidence_score=0.9)

        assert group.base_name == "img_1234"
        assert group.pattern_type == "IMG"
        assert group.confidence_score == 0.9
        assert group.files == []

    def test_file_count_property(self) -> None:
        """Test file_count property."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")
        assert group.file_count == 0

        # Add a file
        file_metadata = FileMetadata(
            file_path=Path("/test/file1.jpg"),
            filename="file1.jpg",
            size_bytes=1000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        group.add_file(file_metadata)
        assert group.file_count == 1

    def test_total_size_mb_property(self) -> None:
        """Test total_size_mb property."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")

        # Add two files
        for i in range(2):
            file_metadata = FileMetadata(
                file_path=Path(f"/test/file{i}.jpg"),
                filename=f"file{i}.jpg",
                size_bytes=1048576,  # 1 MB each
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            group.add_file(file_metadata)

        assert group.total_size_mb == 2.0

    def test_get_largest_file(self) -> None:
        """Test get_largest_file method."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")

        # Add files of different sizes
        small_file = FileMetadata(
            file_path=Path("/test/small.jpg"),
            filename="small.jpg",
            size_bytes=1000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        large_file = FileMetadata(
            file_path=Path("/test/large.jpg"),
            filename="large.jpg",
            size_bytes=2000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )

        group.add_file(small_file)
        group.add_file(large_file)

        largest = group.get_largest_file()
        assert largest == large_file

    def test_get_largest_file_empty_group(self) -> None:
        """Test get_largest_file with empty group."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")
        assert group.get_largest_file() is None

    def test_get_newest_file(self) -> None:
        """Test get_newest_file method."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")

        old_time = datetime(2023, 1, 1)
        new_time = datetime(2023, 12, 31)

        old_file = FileMetadata(
            file_path=Path("/test/old.jpg"),
            filename="old.jpg",
            size_bytes=1000,
            created_at=old_time,
            modified_at=old_time,
        )
        new_file = FileMetadata(
            file_path=Path("/test/new.jpg"),
            filename="new.jpg",
            size_bytes=1000,
            created_at=new_time,
            modified_at=new_time,
        )

        group.add_file(old_file)
        group.add_file(new_file)

        newest = group.get_newest_file()
        assert newest == new_file

    def test_str_representation(self) -> None:
        """Test string representation."""
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")

        file_metadata = FileMetadata(
            file_path=Path("/test/file.jpg"),
            filename="file.jpg",
            size_bytes=1048576,  # 1 MB
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        group.add_file(file_metadata)

        expected = "Duplicate group 'test' (1 files, 1.0 MB)"
        assert str(group) == expected


class TestScanResult:
    """Test cases for ScanResult model."""

    def test_create_scan_result(self) -> None:
        """Test creating a ScanResult object."""
        scan_path = Path("/test/scan")
        result = ScanResult(
            scan_path=scan_path,
            total_files_found=100,
            media_files_found=80,
            scan_duration_seconds=5.5,
        )

        assert result.scan_path == scan_path
        assert result.total_files_found == 100
        assert result.media_files_found == 80
        assert result.scan_duration_seconds == 5.5
        assert result.duplicate_groups == []

    def test_potential_duplicates_count(self) -> None:
        """Test potential_duplicates_count property."""
        result = ScanResult(
            scan_path=Path("/test"),
            total_files_found=10,
            media_files_found=10,
            scan_duration_seconds=1.0,
        )

        # Add a group with 3 files (3 potential duplicates)
        group1 = DuplicateGroup(base_name="test1", pattern_type="GENERIC")
        for i in range(3):
            file_metadata = FileMetadata(
                file_path=Path(f"/test/file{i}.jpg"),
                filename=f"file{i}.jpg",
                size_bytes=1000,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            group1.add_file(file_metadata)

        # Add a group with 1 file (0 potential duplicates)
        group2 = DuplicateGroup(base_name="test2", pattern_type="GENERIC")
        file_metadata = FileMetadata(
            file_path=Path("/test/single.jpg"),
            filename="single.jpg",
            size_bytes=1000,
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        group2.add_file(file_metadata)

        result.duplicate_groups = [group1, group2]

        # Only group1 has multiple files, so 3 potential duplicates
        assert result.potential_duplicates_count == 3

    def test_potential_space_savings_mb(self) -> None:
        """Test potential_space_savings_mb property."""
        result = ScanResult(
            scan_path=Path("/test"),
            total_files_found=4,
            media_files_found=4,
            scan_duration_seconds=1.0,
        )

        # Create a group with files of different sizes
        group = DuplicateGroup(base_name="test", pattern_type="GENERIC")

        # Add 1MB, 2MB, and 3MB files
        sizes = [1048576, 2097152, 3145728]  # 1MB, 2MB, 3MB
        for i, size in enumerate(sizes):
            file_metadata = FileMetadata(
                file_path=Path(f"/test/file{i}.jpg"),
                filename=f"file{i}.jpg",
                size_bytes=size,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            group.add_file(file_metadata)

        result.duplicate_groups = [group]

        # Total size: 6MB, largest file: 3MB, potential savings: 6-3=3MB
        assert result.potential_space_savings_mb == 3.0

    def test_str_representation(self) -> None:
        """Test string representation."""
        result = ScanResult(
            scan_path=Path("/test/scan"),
            total_files_found=100,
            media_files_found=80,
            scan_duration_seconds=5.5,
        )

        expected = "Scan of /test/scan: 80 media files, 0 duplicate groups, 0 potential duplicates"
        assert str(result) == expected


class TestApplicationConfig:
    """Test cases for ApplicationConfig model."""

    def test_create_default_config(self) -> None:
        """Test creating ApplicationConfig with defaults."""
        config = ApplicationConfig()

        assert isinstance(config.supported_extensions, list)
        assert ".jpg" in config.supported_extensions
        assert ".mp4" in config.supported_extensions
        assert config.max_preview_size_mb == 50.0
        assert config.enable_logging is True
        assert config.log_level == "INFO"

    def test_extension_validation(self) -> None:
        """Test that extensions are properly validated."""
        config = ApplicationConfig(supported_extensions=["jpg", "PNG", ".mp4", "HEIC"])

        # All should be lowercase with leading dots
        expected = [".jpg", ".png", ".mp4", ".heic"]
        assert config.supported_extensions == expected
