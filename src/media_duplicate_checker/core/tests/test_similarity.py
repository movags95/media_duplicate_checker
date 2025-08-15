"""Tests for similarity analysis functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from ..models import FileMetadata
from ..similarity import SimilarityAnalyzer, SuffixDetector


class TestSimilarityAnalyzer:
    """Test cases for SimilarityAnalyzer."""

    def test_init_with_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        analyzer = SimilarityAnalyzer(image_threshold=0.95, video_threshold=0.80)
        assert analyzer.image_threshold == 0.95
        assert analyzer.video_threshold == 0.80

    def test_get_media_type(self):
        """Test media type detection from extensions."""
        analyzer = SimilarityAnalyzer()
        
        assert analyzer._get_media_type(".jpg") == "image"
        assert analyzer._get_media_type(".png") == "image"
        assert analyzer._get_media_type(".heic") == "image"
        assert analyzer._get_media_type(".mp4") == "video"
        assert analyzer._get_media_type(".mov") == "video"
        assert analyzer._get_media_type(".txt") == "unknown"

    def test_calculate_similarity_different_types(self):
        """Test that similarity calculation fails for different media types."""
        analyzer = SimilarityAnalyzer()
        
        with tempfile.NamedTemporaryFile(suffix=".jpg") as img_file, \
             tempfile.NamedTemporaryFile(suffix=".mp4") as vid_file:
            
            img_meta = FileMetadata(
                file_path=Path(img_file.name),
                filename="test.jpg",
                size_bytes=1000,
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            vid_meta = FileMetadata(
                file_path=Path(vid_file.name),
                filename="test.mp4",
                size_bytes=2000,
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            with pytest.raises(ValueError, match="Cannot compare files of different media types"):
                analyzer.calculate_similarity(img_meta, vid_meta)

    def test_calculate_similarity_nonexistent_files(self):
        """Test similarity calculation with nonexistent files."""
        analyzer = SimilarityAnalyzer()
        
        file1 = FileMetadata(
            file_path=Path("/nonexistent/file1.jpg"),
            filename="file1.jpg",
            size_bytes=1000,
            created_at=pytest.test_datetime,
            modified_at=pytest.test_datetime
        )
        
        file2 = FileMetadata(
            file_path=Path("/nonexistent/file2.jpg"),
            filename="file2.jpg",
            size_bytes=1000,
            created_at=pytest.test_datetime,
            modified_at=pytest.test_datetime
        )
        
        with pytest.raises(ValueError, match="One or both files do not exist"):
            analyzer.calculate_similarity(file1, file2)

    def test_calculate_video_similarity_by_size(self):
        """Test video similarity calculation based on file size."""
        analyzer = SimilarityAnalyzer()
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as file1, \
             tempfile.NamedTemporaryFile(suffix=".mp4") as file2:
            
            # Write some data to create different file sizes
            file1.write(b"x" * 1000)
            file2.write(b"x" * 1000)  # Same size
            file1.flush()
            file2.flush()
            
            vid1 = FileMetadata(
                file_path=Path(file1.name),
                filename="vid1.mp4",
                size_bytes=1000,
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            vid2 = FileMetadata(
                file_path=Path(file2.name),
                filename="vid2.mp4",
                size_bytes=1000,
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            similarity = analyzer._calculate_video_similarity(vid1, vid2)
            assert similarity >= 0.9  # Identical sizes should score high

    def test_calculate_video_similarity_different_sizes(self):
        """Test video similarity with different file sizes."""
        analyzer = SimilarityAnalyzer()
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as file1, \
             tempfile.NamedTemporaryFile(suffix=".mp4") as file2:
            
            vid1 = FileMetadata(
                file_path=Path(file1.name),
                filename="vid1.mp4",
                size_bytes=1000,
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            vid2 = FileMetadata(
                file_path=Path(file2.name),
                filename="vid2.mp4",
                size_bytes=500,  # Half the size
                created_at=pytest.test_datetime,
                modified_at=pytest.test_datetime
            )
            
            similarity = analyzer._calculate_video_similarity(vid1, vid2)
            assert 0.4 < similarity < 0.6  # Should be moderate similarity

    @patch('imagehash.dhash')
    def test_get_image_hash_success(self, mock_dhash):
        """Test successful image hash generation."""
        analyzer = SimilarityAnalyzer()
        mock_hash = Mock()
        mock_dhash.return_value = mock_hash
        
        # Create a small test image
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
            img = Image.new('RGB', (10, 10), color='red')
            img.save(temp_file.name)
            
            result = analyzer._get_image_hash(Path(temp_file.name))
            assert result == mock_hash
            mock_dhash.assert_called_once()

    def test_get_image_hash_invalid_file(self):
        """Test image hash generation with invalid file."""
        analyzer = SimilarityAnalyzer()
        
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"not an image")
            temp_file.flush()
            
            result = analyzer._get_image_hash(Path(temp_file.name))
            assert result is None

    def test_are_visually_similar_threshold(self):
        """Test visual similarity threshold checking."""
        analyzer = SimilarityAnalyzer(image_threshold=0.8)
        
        with patch.object(analyzer, 'calculate_similarity') as mock_calc:
            mock_calc.return_value = 0.9
            
            file1 = Mock()
            file1.extension = ".jpg"
            file2 = Mock()
            file2.extension = ".jpg"
            
            assert analyzer.are_visually_similar(file1, file2) is True
            
            mock_calc.return_value = 0.7
            assert analyzer.are_visually_similar(file1, file2) is False


class TestSuffixDetector:
    """Test cases for SuffixDetector."""

    def test_has_numeric_suffix_common_patterns(self):
        """Test detection of common numeric suffix patterns."""
        detector = SuffixDetector()
        
        # Test cases with numeric suffixes
        assert detector.has_numeric_suffix("image_1.jpg") is True
        assert detector.has_numeric_suffix("photo (2).png") is True
        assert detector.has_numeric_suffix("document - 3.pdf") is True
        assert detector.has_numeric_suffix("file 4.txt") is True
        assert detector.has_numeric_suffix("backup_copy2.zip") is True
        assert detector.has_numeric_suffix("data copy3.csv") is True
        
        # Test cases without numeric suffixes
        assert detector.has_numeric_suffix("original.jpg") is False
        assert detector.has_numeric_suffix("image.png") is False
        assert detector.has_numeric_suffix("photo_backup.pdf") is False

    def test_get_suffix_priority(self):
        """Test suffix priority calculation."""
        detector = SuffixDetector()
        
        # Original file should have priority 0
        assert detector.get_suffix_priority("original.jpg") == 0
        
        # Files with suffixes should have higher priority numbers
        assert detector.get_suffix_priority("original_1.jpg") == 1
        assert detector.get_suffix_priority("original (2).jpg") == 2
        assert detector.get_suffix_priority("original - 5.jpg") == 5
        
        # Copy files
        assert detector.get_suffix_priority("original_copy.jpg") == 1
        assert detector.get_suffix_priority("original copy2.jpg") == 2

    def test_identify_original_single_file(self):
        """Test original identification with single file."""
        detector = SuffixDetector()
        
        file1 = Mock()
        file1.filename = "test.jpg"
        
        result = detector.identify_original([file1])
        assert result == file1

    def test_identify_original_multiple_files(self):
        """Test original identification with multiple files."""
        detector = SuffixDetector()
        
        # Create mock files with different suffix priorities
        original = Mock()
        original.filename = "photo.jpg"  # Priority 0
        
        copy1 = Mock()
        copy1.filename = "photo_1.jpg"  # Priority 1
        
        copy2 = Mock()
        copy2.filename = "photo (2).jpg"  # Priority 2
        
        files = [copy2, copy1, original]  # Mixed order
        result = detector.identify_original(files)
        assert result == original

    def test_identify_original_no_clear_winner(self):
        """Test original identification when all files have suffixes."""
        detector = SuffixDetector()
        
        copy1 = Mock()
        copy1.filename = "photo_1.jpg"  # Priority 1
        
        copy2 = Mock()
        copy2.filename = "photo_2.jpg"  # Priority 2
        
        files = [copy2, copy1]
        result = detector.identify_original(files)
        assert result == copy1  # Lower priority wins

    def test_identify_original_empty_list(self):
        """Test original identification with empty list."""
        detector = SuffixDetector()
        
        result = detector.identify_original([])
        assert result is None


# Test datetime for consistent testing
from datetime import datetime
pytest.test_datetime = datetime(2023, 1, 1, 12, 0, 0)