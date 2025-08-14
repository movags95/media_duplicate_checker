"""File scanning module for discovering media files."""

import logging
import time
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import ApplicationConfig, FileMetadata
from .parser import FilenameParser

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""

    def __call__(self, current: int, total: int | None = None, message: str = "") -> None:
        """Called to report progress during scanning."""
        ...


class MediaFileScanner:
    """Scans directories for media files and extracts metadata."""

    def __init__(self, config: ApplicationConfig | None = None):
        """
        Initialize the scanner with configuration.

        Args:
            config: Application configuration, defaults to ApplicationConfig()
        """
        self.config = config or ApplicationConfig()
        self.parser = FilenameParser()

    def is_media_file(self, file_path: Path) -> bool:
        """
        Check if a file is a supported media file based on extension.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file is a supported media type, False otherwise
        """
        extension = file_path.suffix.lower()
        return extension in self.config.supported_extensions

    def get_file_metadata(self, file_path: Path) -> FileMetadata | None:
        """
        Extract metadata from a single file.

        Args:
            file_path: Path to the file

        Returns:
            FileMetadata object if successful, None if error occurs

        Raises:
            OSError: If file cannot be accessed
        """
        try:
            if not file_path.exists():
                logger.warning(f"File does not exist: {file_path}")
                return None

            if not file_path.is_file():
                logger.warning(f"Path is not a file: {file_path}")
                return None

            stat = file_path.stat()

            # Parse filename for duplicate detection
            parsed_filename = self.parser.parse_filename(file_path.name)

            return FileMetadata(
                file_path=file_path,
                filename=file_path.name,
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                parsed_filename=parsed_filename,
            )

        except (OSError, PermissionError) as e:
            logger.error(f"Error accessing file {file_path}: {e}")
            return None

    def discover_files(
        self,
        directory: Path,
        recursive: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> Generator[Path, None, None]:
        """
        Discover all files in a directory, optionally recursively.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories recursively
            progress_callback: Optional callback for progress updates

        Yields:
            Path objects for discovered files

        Raises:
            OSError: If directory cannot be accessed
        """
        if not directory.exists():
            raise OSError(f"Directory does not exist: {directory}")

        if not directory.is_dir():
            raise OSError(f"Path is not a directory: {directory}")

        logger.info(f"Starting file discovery in: {directory}")
        files_found = 0

        try:
            if recursive:
                # Use rglob for recursive search
                file_iterator = directory.rglob("*")
            else:
                # Use glob for non-recursive search
                file_iterator = directory.glob("*")

            for file_path in file_iterator:
                if file_path.is_file():
                    files_found += 1
                    if progress_callback:
                        progress_callback(
                            files_found,
                            None,  # We don't know total count ahead of time
                            f"Discovered {files_found} files...",
                        )
                    yield file_path

        except (OSError, PermissionError) as e:
            logger.error(f"Error scanning directory {directory}: {e}")
            raise

        logger.info(f"File discovery complete. Found {files_found} total files.")

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> list[FileMetadata]:
        """
        Scan a directory for media files and return metadata.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories recursively
            progress_callback: Optional callback for progress updates

        Returns:
            List of FileMetadata objects for all discovered media files

        Raises:
            OSError: If directory cannot be accessed
        """
        start_time = time.time()
        media_files = []
        total_files = 0

        logger.info(f"Starting media file scan: {directory}")

        try:
            # First pass: discover all files
            all_files = list(self.discover_files(directory, recursive, progress_callback))
            total_files = len(all_files)

            logger.info(f"Found {total_files} total files, filtering for media files...")

            # Second pass: filter and process media files
            for i, file_path in enumerate(all_files):
                if progress_callback:
                    progress_callback(i + 1, total_files, f"Processing {file_path.name}...")

                if self.is_media_file(file_path):
                    metadata = self.get_file_metadata(file_path)
                    if metadata:
                        media_files.append(metadata)

        except Exception as e:
            logger.error(f"Error during directory scan: {e}")
            raise

        scan_duration = time.time() - start_time
        logger.info(
            f"Scan complete: {len(media_files)} media files found "
            f"out of {total_files} total files in {scan_duration:.2f} seconds"
        )

        return media_files

    def scan_files(
        self, file_paths: list[Path], progress_callback: ProgressCallback | None = None
    ) -> list[FileMetadata]:
        """
        Scan a specific list of files for metadata.

        Args:
            file_paths: List of file paths to scan
            progress_callback: Optional callback for progress updates

        Returns:
            List of FileMetadata objects for valid media files
        """
        start_time = time.time()
        media_files = []
        total_files = len(file_paths)

        logger.info(f"Scanning {total_files} specific files")

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(i + 1, total_files, f"Processing {file_path.name}...")

            if self.is_media_file(file_path):
                metadata = self.get_file_metadata(file_path)
                if metadata:
                    media_files.append(metadata)

        scan_duration = time.time() - start_time
        logger.info(
            f"File scan complete: {len(media_files)} media files processed "
            f"in {scan_duration:.2f} seconds"
        )

        return media_files
