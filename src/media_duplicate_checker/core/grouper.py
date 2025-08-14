"""Duplicate grouping module for organizing potential duplicates."""

import logging
from collections import defaultdict

from .models import DuplicateGroup, FileMetadata
from .parser import FilenameParser

logger = logging.getLogger(__name__)


class DuplicateGrouper:
    """Groups files by potential duplicate patterns."""

    def __init__(self):
        """Initialize the grouper with a filename parser."""
        self.parser = FilenameParser()

    def group_by_base_name(self, files: list[FileMetadata]) -> dict[str, list[FileMetadata]]:
        """
        Group files by their parsed base names.

        Args:
            files: List of file metadata objects to group

        Returns:
            Dictionary mapping base names to lists of files

        Example:
            >>> grouper = DuplicateGrouper()
            >>> files = [file1, file2, file3]  # FileMetadata objects
            >>> groups = grouper.group_by_base_name(files)
            >>> groups["img_1234"]  # [file1, file2]
        """
        groups: dict[str, list[FileMetadata]] = defaultdict(list)

        for file in files:
            # Skip files that couldn't be parsed
            if not file.parsed_filename:
                logger.debug(f"Skipping unparsed file: {file.filename}")
                continue

            # Create a composite key: pattern_type:base_name
            # This ensures files with the same base name but different patterns
            # don't get grouped together (e.g., GUID vs IMG with similar names)
            key = f"{file.parsed_filename.pattern_type}:{file.parsed_filename.base_name}"
            groups[key].append(file)

        logger.info(f"Grouped {len(files)} files into {len(groups)} base name groups")
        return groups

    def create_duplicate_groups(self, files: list[FileMetadata]) -> list[DuplicateGroup]:
        """
        Create duplicate groups from a list of files.

        Args:
            files: List of file metadata objects to analyze

        Returns:
            List of DuplicateGroup objects for potential duplicates

        Only creates groups for base names that have multiple files.
        Single files are not considered duplicates.
        """
        base_name_groups = self.group_by_base_name(files)
        duplicate_groups = []

        for composite_key, file_list in base_name_groups.items():
            # Only create duplicate groups for multiple files
            if len(file_list) < 2:
                continue

            # Extract pattern type and base name from composite key
            pattern_type, base_name = composite_key.split(":", 1)

            # Calculate confidence score based on the pattern type
            confidence_score = self.calculate_group_confidence(file_list)

            duplicate_group = DuplicateGroup(
                base_name=base_name,
                pattern_type=pattern_type,
                files=file_list,
                confidence_score=confidence_score,
            )

            duplicate_groups.append(duplicate_group)
            logger.debug(
                f"Created duplicate group: {base_name} "
                f"({len(file_list)} files, confidence: {confidence_score:.2f})"
            )

        # Sort groups by confidence score (highest first), then by file count
        duplicate_groups.sort(key=lambda g: (-g.confidence_score, -g.file_count))

        logger.info(f"Created {len(duplicate_groups)} duplicate groups")
        return duplicate_groups

    def calculate_group_confidence(self, files: list[FileMetadata]) -> float:
        """
        Calculate confidence score for a group of potential duplicates.

        Args:
            files: List of files in the group

        Returns:
            Confidence score between 0.0 and 1.0

        Confidence is based on:
        - Pattern type (GUID > IMG > GENERIC)
        - File size similarity
        - Creation time proximity
        """
        if not files:
            return 0.0

        # Base confidence from pattern type
        pattern_confidences = []
        for file in files:
            if file.parsed_filename:
                confidence = self.parser.get_pattern_confidence(file.filename)
                pattern_confidences.append(confidence)

        if not pattern_confidences:
            return 0.0

        base_confidence = max(pattern_confidences)

        # Bonus for file size similarity
        size_bonus = self._calculate_size_similarity_bonus(files)

        # Bonus for creation time proximity
        time_bonus = self._calculate_time_proximity_bonus(files)

        # Combine scores (weighted average)
        final_confidence = (
            base_confidence * 0.7  # Pattern type is most important
            + size_bonus * 0.2  # Size similarity is moderately important
            + time_bonus * 0.1  # Time proximity is least important
        )

        # Ensure we don't exceed 1.0
        return min(final_confidence, 1.0)

    def _calculate_size_similarity_bonus(self, files: list[FileMetadata]) -> float:
        """
        Calculate bonus based on file size similarity.

        Args:
            files: List of files to analyze

        Returns:
            Bonus score between 0.0 and 0.3
        """
        if len(files) < 2:
            return 0.0

        sizes = [file.size_bytes for file in files]
        min_size = min(sizes)
        max_size = max(sizes)

        if min_size == 0:
            return 0.0

        # Calculate size variation ratio
        size_ratio = min_size / max_size

        # Convert to bonus score (higher ratio = higher bonus)
        return size_ratio * 0.3

    def _calculate_time_proximity_bonus(self, files: list[FileMetadata]) -> float:
        """
        Calculate bonus based on creation time proximity.

        Args:
            files: List of files to analyze

        Returns:
            Bonus score between 0.0 and 0.2
        """
        if len(files) < 2:
            return 0.0

        timestamps = [file.created_at.timestamp() for file in files]
        time_span = max(timestamps) - min(timestamps)

        # Files created within an hour get maximum bonus
        if time_span <= 3600:  # 1 hour
            return 0.2
        # Files created within a day get moderate bonus
        if time_span <= 86400:  # 1 day
            return 0.1
        # Files created within a week get small bonus
        if time_span <= 604800:  # 1 week
            return 0.05
        return 0.0

    def find_exact_duplicates(self, files: list[FileMetadata]) -> list[DuplicateGroup]:
        """
        Find files that are likely exact duplicates based on size and name.

        Args:
            files: List of files to analyze

        Returns:
            List of high-confidence duplicate groups

        This method is more aggressive and looks for files with identical
        sizes and very similar names, which are very likely to be duplicates.
        """
        # Group by size first for efficiency
        size_groups: dict[int, list[FileMetadata]] = defaultdict(list)
        for file in files:
            size_groups[file.size_bytes].append(file)

        exact_duplicates = []

        for size, same_size_files in size_groups.items():
            if len(same_size_files) < 2:
                continue

            # Within each size group, look for filename patterns
            duplicate_groups = self.create_duplicate_groups(same_size_files)

            # Mark high-confidence groups as exact duplicates
            for group in duplicate_groups:
                if group.confidence_score >= 0.8:  # High confidence threshold
                    group.confidence_score = min(group.confidence_score + 0.1, 1.0)
                    exact_duplicates.append(group)

        logger.info(f"Found {len(exact_duplicates)} exact duplicate groups")
        return exact_duplicates
