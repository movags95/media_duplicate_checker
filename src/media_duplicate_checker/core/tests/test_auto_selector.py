"""Tests for auto-selection functionality."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ..auto_selector import AutoSelector, AutoSelectionResult, GroupFilter
from ..models import DuplicateGroup, FileMetadata


class TestAutoSelector:
    """Test cases for AutoSelector."""

    def create_mock_file(self, filename: str, size: int = 1000) -> FileMetadata:
        """Create a mock FileMetadata object."""
        return FileMetadata(
            file_path=Path(f"/test/{filename}"),
            filename=filename,
            size_bytes=size,
            created_at=datetime.now(),
            modified_at=datetime.now()
        )

    def create_mock_group(self, base_name: str, files: list[FileMetadata]) -> DuplicateGroup:
        """Create a mock DuplicateGroup object."""
        return DuplicateGroup(
            base_name=base_name,
            pattern_type="TEST",
            files=files,
            confidence_score=0.9
        )

    def test_init_with_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        selector = AutoSelector(
            image_similarity_threshold=0.95,
            video_similarity_threshold=0.80,
            min_confidence_threshold=0.75
        )
        
        assert selector.similarity_analyzer.image_threshold == 0.95
        assert selector.similarity_analyzer.video_threshold == 0.80
        assert selector.min_confidence_threshold == 0.75

    def test_analyze_group_wrong_file_count(self):
        """Test that groups with not exactly 2 files are skipped."""
        selector = AutoSelector()
        
        # Test single file
        single_file = self.create_mock_file("test.jpg")
        single_group = self.create_mock_group("test", [single_file])
        
        result = selector.analyze_group(single_group)
        assert result is None
        
        # Test three files
        files = [
            self.create_mock_file("test1.jpg"),
            self.create_mock_file("test2.jpg"),
            self.create_mock_file("test3.jpg")
        ]
        triple_group = self.create_mock_group("test", files)
        
        result = selector.analyze_group(triple_group)
        assert result is None

    @patch('media_duplicate_checker.core.auto_selector.SimilarityAnalyzer')
    def test_analyze_group_not_similar(self, mock_analyzer_class):
        """Test that non-similar files are not auto-selected."""
        mock_analyzer = Mock()
        mock_analyzer.are_visually_similar.return_value = False
        mock_analyzer_class.return_value = mock_analyzer
        
        selector = AutoSelector()
        selector.similarity_analyzer = mock_analyzer
        
        files = [
            self.create_mock_file("test.jpg"),
            self.create_mock_file("test_1.jpg")
        ]
        group = self.create_mock_group("test", files)
        
        result = selector.analyze_group(group)
        assert result is None

    @patch('media_duplicate_checker.core.auto_selector.SimilarityAnalyzer')
    @patch('media_duplicate_checker.core.auto_selector.SuffixDetector')
    def test_analyze_group_successful(self, mock_suffix_class, mock_analyzer_class):
        """Test successful auto-selection analysis."""
        # Mock similarity analyzer
        mock_analyzer = Mock()
        mock_analyzer.are_visually_similar.return_value = True
        mock_analyzer.calculate_similarity.return_value = 0.95
        mock_analyzer_class.return_value = mock_analyzer
        
        # Mock suffix detector
        mock_suffix = Mock()
        mock_suffix.identify_original.return_value = Mock()
        mock_suffix.get_suffix_priority.side_effect = [0, 1]  # First file original, second is copy
        mock_suffix_class.return_value = mock_suffix
        
        selector = AutoSelector()
        selector.similarity_analyzer = mock_analyzer
        selector.suffix_detector = mock_suffix
        
        file1 = self.create_mock_file("test.jpg")
        file2 = self.create_mock_file("test_1.jpg")
        mock_suffix.identify_original.return_value = file1
        
        files = [file1, file2]
        group = self.create_mock_group("test", files)
        
        result = selector.analyze_group(group)
        
        assert result is not None
        assert isinstance(result, AutoSelectionResult)
        assert result.group == group
        assert file1.file_path in result.files_to_keep
        assert file2.file_path in result.files_to_delete
        assert result.confidence > 0.8

    def test_can_auto_select_threshold(self):
        """Test confidence threshold checking."""
        selector = AutoSelector(min_confidence_threshold=0.8)
        
        high_confidence = AutoSelectionResult(
            group=Mock(),
            files_to_delete=set(),
            files_to_keep=set(),
            confidence=0.9,
            reasoning="Test"
        )
        
        low_confidence = AutoSelectionResult(
            group=Mock(),
            files_to_delete=set(),
            files_to_keep=set(),
            confidence=0.7,
            reasoning="Test"
        )
        
        assert selector.can_auto_select(high_confidence) is True
        assert selector.can_auto_select(low_confidence) is False

    @patch.object(AutoSelector, 'analyze_group')
    def test_process_groups(self, mock_analyze):
        """Test processing multiple groups."""
        selector = AutoSelector()
        
        # Create mock results
        auto_result = AutoSelectionResult(
            group=Mock(),
            files_to_delete=set(),
            files_to_keep=set(),
            confidence=0.9,
            reasoning="High confidence"
        )
        
        low_conf_result = AutoSelectionResult(
            group=Mock(),
            files_to_delete=set(),
            files_to_keep=set(),
            confidence=0.7,
            reasoning="Low confidence"
        )
        
        mock_analyze.side_effect = [auto_result, low_conf_result, None]
        
        groups = [Mock(), Mock(), Mock()]
        results = selector.process_groups(groups)
        
        assert len(results['auto_selected']) == 1
        assert len(results['low_confidence']) == 1
        assert len(results['skipped']) == 1

    def test_get_auto_selection_summary(self):
        """Test summary generation."""
        selector = AutoSelector()
        
        auto_result = AutoSelectionResult(
            group=Mock(),
            files_to_delete={Path("/test1.jpg")},
            files_to_keep=set(),
            confidence=0.9,
            reasoning="Test"
        )
        
        results = {
            'auto_selected': [auto_result],
            'low_confidence': [],
            'skipped': []
        }
        
        summary = selector.get_auto_selection_summary(results)
        assert "1 groups auto-selected" in summary
        assert "1 files marked for deletion" in summary

    def test_get_auto_selection_summary_empty(self):
        """Test summary with no results."""
        selector = AutoSelector()
        
        results = {
            'auto_selected': [],
            'low_confidence': [],
            'skipped': []
        }
        
        summary = selector.get_auto_selection_summary(results)
        assert summary == "No groups processed"


class TestGroupFilter:
    """Test cases for GroupFilter."""

    def create_mock_result(self, group_name: str, applied: bool = True) -> AutoSelectionResult:
        """Create a mock AutoSelectionResult."""
        group = Mock()
        group.base_name = group_name
        
        return AutoSelectionResult(
            group=group,
            files_to_delete=set(),
            files_to_keep=set(),
            confidence=0.9,
            reasoning="Test",
            applied=applied
        )

    def test_filter_by_resolution_status_all(self):
        """Test filtering with 'all' status."""
        group1 = Mock()
        group1.base_name = "group1"
        group2 = Mock()
        group2.base_name = "group2"
        
        groups = [group1, group2]
        auto_results = []
        
        filtered = GroupFilter.filter_by_resolution_status(groups, auto_results, 'all')
        assert len(filtered) == 2

    def test_filter_by_resolution_status_resolved(self):
        """Test filtering for resolved groups."""
        group1 = Mock()
        group1.base_name = "group1"
        group2 = Mock()
        group2.base_name = "group2"
        
        groups = [group1, group2]
        auto_results = [self.create_mock_result("group1", applied=True)]
        
        filtered = GroupFilter.filter_by_resolution_status(groups, auto_results, 'resolved')
        assert len(filtered) == 1
        assert filtered[0].base_name == "group1"

    def test_filter_by_resolution_status_unresolved(self):
        """Test filtering for unresolved groups."""
        group1 = Mock()
        group1.base_name = "group1"
        group2 = Mock()
        group2.base_name = "group2"
        
        groups = [group1, group2]
        auto_results = [self.create_mock_result("group1", applied=True)]
        
        filtered = GroupFilter.filter_by_resolution_status(groups, auto_results, 'unresolved')
        assert len(filtered) == 1
        assert filtered[0].base_name == "group2"

    def test_get_unresolved_count(self):
        """Test counting unresolved groups."""
        group1 = Mock()
        group1.base_name = "group1"
        group2 = Mock()
        group2.base_name = "group2"
        group3 = Mock()
        group3.base_name = "group3"
        
        groups = [group1, group2, group3]
        auto_results = [self.create_mock_result("group1", applied=True)]
        
        count = GroupFilter.get_unresolved_count(groups, auto_results)
        assert count == 2

    def test_filter_invalid_status(self):
        """Test filtering with invalid status."""
        groups = [Mock()]
        auto_results = []
        
        # Invalid status should return all groups
        filtered = GroupFilter.filter_by_resolution_status(groups, auto_results, 'invalid')
        assert len(filtered) == len(groups)