"""Filename parsing module for detecting duplicate patterns."""

import re

from .models import ParsedFilename


class FilenameParser:
    """Parses filenames to extract components for duplicate detection."""

    # GUID pattern: 8-4-4-4-12 hexadecimal characters
    GUID_PATTERN = re.compile(
        r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
        r"(-\d+)?(\.[^.]+)$"
    )

    # IMG prefix pattern: IMG_followed by numbers
    IMG_PATTERN = re.compile(r"^(IMG_\d+)(-\d+)?(\.[^.]+)$", re.IGNORECASE)

    # Generic numbered file pattern: basename followed by numbers in parentheses or with dash
    NUMBERED_PATTERN = re.compile(r"^(.+?)(?:\s*\(\d+\)|\s*-\d+|\s*_\d+)?(\.[^.]+)$", re.IGNORECASE)

    def parse_filename(self, filename: str) -> ParsedFilename | None:
        """
        Parse a filename to extract components for duplicate detection.

        Args:
            filename: The filename to parse

        Returns:
            ParsedFilename object if pattern is recognized, None otherwise

        Example:
            >>> parser = FilenameParser()
            >>> result = parser.parse_filename("58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG")
            >>> result.base_name
            '58c9b580-5303-4b3b-b75d-f07f505f8d59'
        """
        if not filename or not isinstance(filename, str):
            return None

        # Try GUID pattern first (highest priority)
        guid_match = self.GUID_PATTERN.match(filename)
        if guid_match:
            base_name = guid_match.group(1)
            suffix = guid_match.group(2)[1:] if guid_match.group(2) else None  # Remove leading dash
            extension = guid_match.group(3)
            return ParsedFilename(
                original_name=filename,
                base_name=base_name.lower(),  # Normalize case
                suffix=suffix,
                extension=extension,
                pattern_type="GUID",
            )

        # Try IMG pattern
        img_match = self.IMG_PATTERN.match(filename)
        if img_match:
            base_name = img_match.group(1)
            suffix = img_match.group(2)[1:] if img_match.group(2) else None  # Remove leading dash
            extension = img_match.group(3)
            return ParsedFilename(
                original_name=filename,
                base_name=base_name.lower(),  # Normalize case
                suffix=suffix,
                extension=extension,
                pattern_type="IMG",
            )

        # Try generic numbered pattern (lowest priority)
        numbered_match = self.NUMBERED_PATTERN.match(filename)
        if numbered_match:
            base_name = numbered_match.group(1).strip()
            extension = numbered_match.group(2)

            # Only consider it a pattern if the base name is meaningful
            if len(base_name) >= 3:  # Arbitrary minimum length
                return ParsedFilename(
                    original_name=filename,
                    base_name=base_name.lower(),  # Normalize case
                    suffix=None,
                    extension=extension,
                    pattern_type="GENERIC",
                )

        return None

    def are_potential_duplicates(self, filename1: str, filename2: str) -> bool:
        """
        Check if two filenames are potential duplicates based on their base names.

        Args:
            filename1: First filename to compare
            filename2: Second filename to compare

        Returns:
            True if the files are potential duplicates, False otherwise

        Example:
            >>> parser = FilenameParser()
            >>> parser.are_potential_duplicates("IMG_1234.HEIC", "IMG_1234-56788.HEIC")
            True
        """
        parsed1 = self.parse_filename(filename1)
        parsed2 = self.parse_filename(filename2)

        if not parsed1 or not parsed2:
            return False

        # Must have same pattern type and base name to be considered duplicates
        return (
            parsed1.pattern_type == parsed2.pattern_type and parsed1.base_name == parsed2.base_name
        )

    def extract_base_name(self, filename: str) -> str | None:
        """
        Extract just the base name from a filename for grouping purposes.

        Args:
            filename: The filename to extract base name from

        Returns:
            Base name if pattern is recognized, None otherwise
        """
        parsed = self.parse_filename(filename)
        return parsed.base_name if parsed else None

    def get_pattern_confidence(self, filename: str) -> float:
        """
        Get confidence score for how likely this filename pattern indicates duplicates.

        Args:
            filename: The filename to evaluate

        Returns:
            Confidence score between 0.0 and 1.0

        GUID patterns have highest confidence (0.95)
        IMG patterns have high confidence (0.90)
        Generic patterns have lower confidence (0.70)
        """
        parsed = self.parse_filename(filename)
        if not parsed:
            return 0.0

        confidence_map = {
            "GUID": 0.95,
            "IMG": 0.90,
            "GENERIC": 0.70,
        }

        return confidence_map.get(parsed.pattern_type, 0.0)
