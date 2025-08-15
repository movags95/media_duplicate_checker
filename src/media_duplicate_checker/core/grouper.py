"""Duplicate grouping module for organizing potential duplicates."""

import logging
from collections import defaultdict
from typing import Protocol

from .models import ApplicationConfig, DuplicateGroup, FileMetadata
from .parser import FilenameParser
from .similarity import SimilarityAnalyzer

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions during visual filtering."""

    def __call__(self, current: int, total: int | None = None, message: str = "") -> None:
        """Called to report progress during visual filtering."""
        ...


class DuplicateGrouper:
    """Groups files by potential duplicate patterns."""

    def __init__(self, config: ApplicationConfig | None = None):
        """Initialize the grouper with a filename parser and optional config."""
        self.parser = FilenameParser()
        self.config = config or ApplicationConfig()
        self._similarity_analyzer = None
        self._similarity_cache = {}

        # Statistics for visual filtering
        self.visual_filtering_stats = {
            "groups_analyzed": 0,
            "groups_filtered_out": 0,
            "groups_retained": 0,
            "visual_comparisons": 0,
        }

    @property
    def similarity_analyzer(self):
        """Lazily initialize and return the similarity analyzer."""
        if self._similarity_analyzer is None:
            self._similarity_analyzer = SimilarityAnalyzer(
                image_threshold=self.config.visual_filtering_image_threshold,
                video_threshold=self.config.visual_filtering_video_threshold,
            )
        return self._similarity_analyzer

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

    def create_duplicate_groups(
        self, files: list[FileMetadata], progress_callback: ProgressCallback | None = None
    ) -> list[DuplicateGroup]:
        """
        Create duplicate groups from a list of files.

        Args:
            files: List of file metadata objects to analyze
            progress_callback: Optional callback for progress updates during visual filtering

        Returns:
            List of DuplicateGroup objects for potential duplicates

        Only creates groups for base names that have multiple files.
        Single files are not considered duplicates.
        iCloud Live Photos (.HEIC/.MOV pairs) are excluded from duplicate detection.
        Visual filtering is applied if enabled in configuration.
        """
        base_name_groups = self.group_by_base_name(files)
        initial_groups = []

        # First stage: Create initial groups based on filename patterns
        for composite_key, file_list in base_name_groups.items():
            # Only create duplicate groups for multiple files
            if len(file_list) < 2:
                continue

            # Skip iCloud Live Photos pairs (.HEIC/.MOV with same base name)
            if self._is_icloud_live_photos_pair(file_list):
                logger.debug(f"Skipping iCloud Live Photos pair: {composite_key}")
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

            initial_groups.append(duplicate_group)
            logger.debug(
                f"Created initial duplicate group: {base_name} "
                f"({len(file_list)} files, confidence: {confidence_score:.2f})"
            )

        # Second stage: Apply visual filtering if enabled
        if self.config.enable_visual_filtering:
            duplicate_groups = self._apply_visual_filtering(initial_groups, progress_callback)
        else:
            duplicate_groups = initial_groups

        # Sort groups by confidence score (highest first), then by file count
        duplicate_groups.sort(key=lambda g: (-g.confidence_score, -g.file_count))

        # Log results with visual filtering statistics
        if self.config.enable_visual_filtering:
            logger.info(
                f"Created {len(duplicate_groups)} duplicate groups after visual filtering "
                f"(filtered out {self.visual_filtering_stats['groups_filtered_out']} groups, "
                f"{self.visual_filtering_stats['visual_comparisons']} visual comparisons)"
            )
        else:
            logger.info(f"Created {len(duplicate_groups)} duplicate groups")

        return duplicate_groups

    def _apply_visual_filtering(
        self, groups: list[DuplicateGroup], progress_callback: ProgressCallback | None = None
    ) -> list[DuplicateGroup]:
        """
        Apply visual similarity filtering to groups.

        Args:
            groups: Initial groups to filter
            progress_callback: Optional callback for progress updates

        Returns:
            Filtered list of groups containing only visually similar files
        """
        logger.info(f"Applying visual filtering to {len(groups)} groups...")

        # Reset statistics
        self.visual_filtering_stats = {
            "groups_analyzed": 0,
            "groups_filtered_out": 0,
            "groups_retained": 0,
            "visual_comparisons": 0,
        }

        filtered_groups = []

        for i, group in enumerate(groups):
            if progress_callback:
                progress_callback(
                    i + 1,
                    len(groups),
                    f"Visual analysis: {group.base_name} ({len(group.files)} files)",
                )

            self.visual_filtering_stats["groups_analyzed"] += 1

            # Skip visual filtering for groups that are too large (performance)
            if len(group.files) > self.config.visual_filtering_max_group_size:
                logger.debug(
                    f"Skipping visual filtering for large group {group.base_name} "
                    f"({len(group.files)} files > {self.config.visual_filtering_max_group_size})"
                )
                filtered_groups.append(group)
                self.visual_filtering_stats["groups_retained"] += 1
                continue

            # Apply visual filtering to the group
            visually_similar_files = self._filter_group_by_visual_similarity(group.files)

            if len(visually_similar_files) >= 2:
                # Update the group with filtered files
                filtered_group = DuplicateGroup(
                    base_name=group.base_name,
                    pattern_type=group.pattern_type,
                    files=visually_similar_files,
                    confidence_score=group.confidence_score,
                )
                filtered_groups.append(filtered_group)
                self.visual_filtering_stats["groups_retained"] += 1

                if len(visually_similar_files) < len(group.files):
                    logger.debug(
                        f"Visual filtering reduced group {group.base_name} from "
                        f"{len(group.files)} to {len(visually_similar_files)} files"
                    )
            else:
                # Group was filtered out entirely
                self.visual_filtering_stats["groups_filtered_out"] += 1
                logger.debug(
                    f"Visual filtering removed group {group.base_name} "
                    f"(no visually similar files found)"
                )

        logger.info(
            f"Visual filtering complete: {len(filtered_groups)} groups retained, "
            f"{self.visual_filtering_stats['groups_filtered_out']} filtered out"
        )

        return filtered_groups

    def _filter_group_by_visual_similarity(self, files: list[FileMetadata]) -> list[FileMetadata]:
        """
        Filter files in a group to only include visually similar ones.

        Args:
            files: List of files to filter

        Returns:
            List of files that are visually similar to each other
        """
        if len(files) <= 1:
            return files

        # For groups of 2 files, use simple pairwise comparison
        if len(files) == 2:
            file1, file2 = files
            if self._are_files_visually_similar(file1, file2):
                return files
            return []

        # For larger groups, find the largest connected component of similar files
        # This is more complex but ensures we keep the largest group of mutually similar files
        similar_pairs = []

        # Find all pairs of visually similar files
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                if self._are_files_visually_similar(files[i], files[j]):
                    similar_pairs.append((i, j))

        if not similar_pairs:
            return []

        # Build connected components (groups of mutually connected files)
        file_indices = set(range(len(files)))
        components = []

        while file_indices:
            # Start a new component with any remaining file
            start_file = file_indices.pop()
            component = {start_file}

            # Find all files connected to this component
            changed = True
            while changed:
                changed = False
                for i, j in similar_pairs:
                    if i in component and j in file_indices:
                        component.add(j)
                        file_indices.remove(j)
                        changed = True
                    elif j in component and i in file_indices:
                        component.add(i)
                        file_indices.remove(i)
                        changed = True

            components.append(component)

        # Return the files from the largest component
        if components:
            largest_component = max(components, key=len)
            return [files[i] for i in sorted(largest_component)]

        return []

    def _are_files_visually_similar(self, file1: FileMetadata, file2: FileMetadata) -> bool:
        """
        Check if two files are visually similar using cached results.

        Args:
            file1: First file to compare
            file2: Second file to compare

        Returns:
            True if files are visually similar, False otherwise
        """
        # Create cache key (order independent)
        file_paths = tuple(sorted([str(file1.file_path), str(file2.file_path)]))
        cache_key = hash(file_paths)

        # Check cache first
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # Compute similarity
        try:
            is_similar = self.similarity_analyzer.are_visually_similar(file1, file2)
            self.visual_filtering_stats["visual_comparisons"] += 1

            # Cache the result (with size limit)
            if len(self._similarity_cache) < self.config.visual_filtering_cache_size:
                self._similarity_cache[cache_key] = is_similar

            return is_similar

        except Exception as e:
            logger.warning(f"Error comparing {file1.filename} and {file2.filename}: {e}")
            return False

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

    def _is_icloud_live_photos_pair(self, files: list[FileMetadata]) -> bool:
        """
        Check if a group of files represents an iCloud Live Photos pair.

        Args:
            files: List of files to check

        Returns:
            True if files represent an iCloud Live Photos pair (.HEIC + .MOV with same base name)

        iCloud Live Photos consist of:
        - One .HEIC file (photo)
        - One .MOV file (video)
        - Both have the same base filename
        """
        if len(files) != 2:
            return False

        extensions = {file.extension for file in files}
        return extensions == {".heic", ".mov"}  # Extensions are already normalized to lowercase
