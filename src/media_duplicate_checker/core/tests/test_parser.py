"""Tests for filename parser module."""


from ..parser import FilenameParser


class TestFilenameParser:
    """Test cases for FilenameParser class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.parser = FilenameParser()

    def test_parse_guid_filename_basic(self) -> None:
        """Test parsing basic GUID filename without suffix."""
        filename = "58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.original_name == filename
        assert result.base_name == "58c9b580-5303-4b3b-b75d-f07f505f8d59"
        assert result.suffix is None
        assert result.extension == ".jpg"
        assert result.pattern_type == "GUID"

    def test_parse_guid_filename_with_suffix(self) -> None:
        """Test parsing GUID filename with numeric suffix."""
        filename = "58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.original_name == filename
        assert result.base_name == "58c9b580-5303-4b3b-b75d-f07f505f8d59"
        assert result.suffix == "222115"
        assert result.extension == ".jpg"
        assert result.pattern_type == "GUID"

    def test_parse_img_filename_basic(self) -> None:
        """Test parsing basic IMG filename without suffix."""
        filename = "IMG_1234.HEIC"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.original_name == filename
        assert result.base_name == "img_1234"  # Should be normalized to lowercase
        assert result.suffix is None
        assert result.extension == ".heic"
        assert result.pattern_type == "IMG"

    def test_parse_img_filename_with_suffix(self) -> None:
        """Test parsing IMG filename with numeric suffix."""
        filename = "IMG_1234-56788.HEIC"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.original_name == filename
        assert result.base_name == "img_1234"
        assert result.suffix == "56788"
        assert result.extension == ".heic"
        assert result.pattern_type == "IMG"

    def test_parse_img_filename_case_insensitive(self) -> None:
        """Test that IMG pattern matching is case insensitive."""
        filename = "img_5678.jpeg"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.base_name == "img_5678"
        assert result.pattern_type == "IMG"

    def test_parse_generic_filename(self) -> None:
        """Test parsing generic filename with meaningful base name."""
        filename = "vacation_photo.jpg"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.original_name == filename
        assert result.base_name == "vacation_photo"
        assert result.suffix is None
        assert result.extension == ".jpg"
        assert result.pattern_type == "GENERIC"

    def test_parse_generic_filename_too_short(self) -> None:
        """Test that very short base names are rejected."""
        filename = "ab.jpg"
        result = self.parser.parse_filename(filename)

        assert result is None

    def test_parse_invalid_filename(self) -> None:
        """Test handling of invalid or unrecognized filenames."""
        test_cases = [
            "",
            None,
            "a.jpg",  # Too short for GENERIC pattern
            "ab.txt",  # Too short for GENERIC pattern
        ]

        for filename in test_cases:
            result = self.parser.parse_filename(filename)
            assert result is None

    def test_parse_guid_malformed(self) -> None:
        """Test that malformed GUIDs are not matched."""
        test_cases = [
            "58c9b580-5303-4b3b-b75d.JPG",  # Too short
            "58c9b580-5303-4b3b-b75d-f07f505f8d59-extra.JPG",  # Too long
            "not-a-guid-at-all-here-today.JPG",  # Not hex
        ]

        for filename in test_cases:
            result = self.parser.parse_filename(filename)
            # These should either be None or parsed as GENERIC, not GUID
            assert result is None or result.pattern_type != "GUID"

    def test_are_potential_duplicates_same_guid(self) -> None:
        """Test duplicate detection for GUID filenames."""
        filename1 = "58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG"
        filename2 = "58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG"

        assert self.parser.are_potential_duplicates(filename1, filename2)

    def test_are_potential_duplicates_same_img(self) -> None:
        """Test duplicate detection for IMG filenames."""
        filename1 = "IMG_1234.HEIC"
        filename2 = "IMG_1234-56788.HEIC"

        assert self.parser.are_potential_duplicates(filename1, filename2)

    def test_are_potential_duplicates_different_patterns(self) -> None:
        """Test that different pattern types are not considered duplicates."""
        filename1 = "IMG_1234.JPG"
        filename2 = "58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG"

        assert not self.parser.are_potential_duplicates(filename1, filename2)

    def test_are_potential_duplicates_different_base_names(self) -> None:
        """Test that different base names are not considered duplicates."""
        filename1 = "IMG_1234.HEIC"
        filename2 = "IMG_5678.HEIC"

        assert not self.parser.are_potential_duplicates(filename1, filename2)

    def test_extract_base_name_guid(self) -> None:
        """Test base name extraction for GUID."""
        filename = "58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG"
        base_name = self.parser.extract_base_name(filename)

        assert base_name == "58c9b580-5303-4b3b-b75d-f07f505f8d59"

    def test_extract_base_name_img(self) -> None:
        """Test base name extraction for IMG."""
        filename = "IMG_1234-56788.HEIC"
        base_name = self.parser.extract_base_name(filename)

        assert base_name == "img_1234"

    def test_extract_base_name_invalid(self) -> None:
        """Test base name extraction for invalid filename."""
        filename = "ab.txt"  # Too short for GENERIC pattern
        base_name = self.parser.extract_base_name(filename)

        assert base_name is None

    def test_get_pattern_confidence_guid(self) -> None:
        """Test confidence scoring for GUID pattern."""
        filename = "58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG"
        confidence = self.parser.get_pattern_confidence(filename)

        assert confidence == 0.95

    def test_get_pattern_confidence_img(self) -> None:
        """Test confidence scoring for IMG pattern."""
        filename = "IMG_1234.HEIC"
        confidence = self.parser.get_pattern_confidence(filename)

        assert confidence == 0.90

    def test_get_pattern_confidence_generic(self) -> None:
        """Test confidence scoring for generic pattern."""
        filename = "vacation_photo.jpg"
        confidence = self.parser.get_pattern_confidence(filename)

        assert confidence == 0.70

    def test_get_pattern_confidence_invalid(self) -> None:
        """Test confidence scoring for invalid filename."""
        filename = "ab.txt"  # Too short for GENERIC pattern
        confidence = self.parser.get_pattern_confidence(filename)

        assert confidence == 0.0

    def test_extension_normalization(self) -> None:
        """Test that extensions are properly normalized."""
        filename = "IMG_1234.HEIC"
        result = self.parser.parse_filename(filename)

        assert result is not None
        assert result.extension == ".heic"

    def test_case_normalization(self) -> None:
        """Test that base names are normalized to lowercase."""
        filename1 = "IMG_1234.JPG"
        filename2 = "img_1234.jpg"

        result1 = self.parser.parse_filename(filename1)
        result2 = self.parser.parse_filename(filename2)

        assert result1 is not None
        assert result2 is not None
        assert result1.base_name == result2.base_name
        assert self.parser.are_potential_duplicates(filename1, filename2)
