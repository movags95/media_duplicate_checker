"""Auto-selection logic for duplicate file management."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import DuplicateGroup, FileMetadata
from .similarity import SimilarityAnalyzer, SuffixDetector

logger = logging.getLogger(__name__)


@dataclass
class AutoSelectionResult:
    """Result of auto-selection analysis for a duplicate group."""
    
    group: DuplicateGroup
    files_to_delete: Set[Path]
    files_to_keep: Set[Path]
    confidence: float
    reasoning: str
    applied: bool = False


class AutoSelector:
    """Handles automatic selection of files for deletion in duplicate groups."""
    
    def __init__(
        self,
        image_similarity_threshold: float = 0.90,
        video_similarity_threshold: float = 0.85,
        min_confidence_threshold: float = 0.80
    ):
        """
        Initialize the auto selector.
        
        Args:
            image_similarity_threshold: Minimum similarity for image auto-selection
            video_similarity_threshold: Minimum similarity for video auto-selection  
            min_confidence_threshold: Minimum confidence to auto-select
        """
        self.similarity_analyzer = SimilarityAnalyzer(
            image_threshold=image_similarity_threshold,
            video_threshold=video_similarity_threshold
        )
        self.suffix_detector = SuffixDetector()
        self.min_confidence_threshold = min_confidence_threshold
        
    def analyze_group(self, group: DuplicateGroup) -> Optional[AutoSelectionResult]:
        """
        Analyze a duplicate group and determine auto-selection recommendations.
        
        Args:
            group: Duplicate group to analyze
            
        Returns:
            AutoSelectionResult if group can be auto-processed, None otherwise
        """
        # Only process groups with exactly 2 files as requested
        if len(group.files) != 2:
            logger.debug(f"Skipping group {group.base_name}: not exactly 2 files ({len(group.files)})")
            return None
            
        file1, file2 = group.files
        
        try:
            # Check visual similarity
            are_similar = self.similarity_analyzer.are_visually_similar(file1, file2)
            
            if not are_similar:
                logger.debug(f"Files not visually similar in group {group.base_name}")
                return None
                
            # Get similarity score for confidence calculation
            similarity_score = self.similarity_analyzer.calculate_similarity(file1, file2)
            
            # Determine which file to keep based on suffix analysis
            original_file = self.suffix_detector.identify_original([file1, file2])
            
            if original_file is None:
                logger.debug(f"Could not identify original file in group {group.base_name}")
                return None
                
            # Set up files to keep/delete
            files_to_keep = {original_file.file_path}
            files_to_delete = set()
            
            for file in group.files:
                if file.file_path != original_file.file_path:
                    files_to_delete.add(file.file_path)
            
            # Generate reasoning and confidence
            reasoning_parts = []
            confidence_factors = []
            
            # Visual similarity component
            reasoning_parts.append(f"Visual similarity: {similarity_score:.1%}")
            confidence_factors.append(similarity_score * 0.6)  # 60% weight
            
            # Suffix analysis component
            file1_priority = self.suffix_detector.get_suffix_priority(file1.filename)
            file2_priority = self.suffix_detector.get_suffix_priority(file2.filename)
            
            if file1_priority != file2_priority:
                reasoning_parts.append("Numeric suffix detected")
                confidence_factors.append(0.3)  # 30% weight for clear suffix difference
            else:
                reasoning_parts.append("No clear suffix pattern")
                confidence_factors.append(0.1)  # Lower confidence without suffix
            
            # File size component (bonus for identical sizes)
            if file1.size_bytes == file2.size_bytes:
                reasoning_parts.append("Identical file sizes")
                confidence_factors.append(0.1)  # 10% bonus
            else:
                size_ratio = min(file1.size_bytes, file2.size_bytes) / max(file1.size_bytes, file2.size_bytes)
                if size_ratio > 0.95:
                    reasoning_parts.append("Very similar file sizes")
                    confidence_factors.append(0.05)
                
            # Calculate final confidence
            final_confidence = min(sum(confidence_factors), 1.0)
            
            # Create reasoning string
            delete_file = next(f for f in group.files if f.file_path in files_to_delete)
            reasoning = (
                f"Keep '{original_file.filename}', delete '{delete_file.filename}'. "
                f"Reasons: {', '.join(reasoning_parts)}"
            )
            
            result = AutoSelectionResult(
                group=group,
                files_to_delete=files_to_delete,
                files_to_keep=files_to_keep,
                confidence=final_confidence,
                reasoning=reasoning
            )
            
            logger.debug(
                f"Auto-selection for group {group.base_name}: "
                f"confidence={final_confidence:.2f}, reason='{reasoning}'"
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"Error analyzing group {group.base_name}: {e}")
            return None
    
    def can_auto_select(self, result: AutoSelectionResult) -> bool:
        """
        Check if an auto-selection result meets the confidence threshold.
        
        Args:
            result: Auto-selection result to check
            
        Returns:
            True if result can be automatically applied
        """
        return result.confidence >= self.min_confidence_threshold
    
    def process_groups(
        self,
        groups: List[DuplicateGroup],
        apply_selections: bool = False
    ) -> Dict[str, List[AutoSelectionResult]]:
        """
        Process multiple duplicate groups for auto-selection.
        
        Args:
            groups: List of duplicate groups to process
            apply_selections: Whether to mark selections as applied
            
        Returns:
            Dictionary with 'auto_selected', 'low_confidence', and 'skipped' results
        """
        results = {
            'auto_selected': [],
            'low_confidence': [],
            'skipped': []
        }
        
        for group in groups:
            result = self.analyze_group(group)
            
            if result is None:
                results['skipped'].append(group)
                continue
                
            if self.can_auto_select(result):
                if apply_selections:
                    result.applied = True
                results['auto_selected'].append(result)
            else:
                results['low_confidence'].append(result)
        
        logger.info(
            f"Auto-selection results: {len(results['auto_selected'])} auto-selected, "
            f"{len(results['low_confidence'])} low confidence, "
            f"{len(results['skipped'])} skipped"
        )
        
        return results
    
    def get_auto_selection_summary(self, results: Dict[str, List[AutoSelectionResult]]) -> str:
        """
        Generate a summary string of auto-selection results.
        
        Args:
            results: Results from process_groups
            
        Returns:
            Human-readable summary string
        """
        auto_selected = len(results['auto_selected'])
        low_confidence = len(results['low_confidence'])
        skipped = len(results['skipped'])
        
        total_files_to_delete = sum(
            len(result.files_to_delete) for result in results['auto_selected']
        )
        
        summary_parts = []
        
        if auto_selected > 0:
            summary_parts.append(f"{auto_selected} groups auto-selected ({total_files_to_delete} files marked for deletion)")
        
        if low_confidence > 0:
            summary_parts.append(f"{low_confidence} groups with low confidence")
            
        if skipped > 0:
            summary_parts.append(f"{skipped} groups skipped (not 2 files or not similar)")
        
        if not summary_parts:
            return "No groups processed"
            
        return ". ".join(summary_parts) + "."


class GroupFilter:
    """Filters duplicate groups based on auto-selection status."""
    
    @staticmethod
    def filter_by_resolution_status(
        groups: List[DuplicateGroup],
        auto_results: List[AutoSelectionResult],
        status: str
    ) -> List[DuplicateGroup]:
        """
        Filter groups by their resolution status.
        
        Args:
            groups: All duplicate groups
            auto_results: Auto-selection results
            status: Filter status - 'resolved', 'unresolved', 'all'
            
        Returns:
            Filtered list of groups
        """
        if status == 'all':
            return groups
            
        # Create set of group IDs that have been auto-resolved
        auto_resolved_groups = {
            result.group.base_name for result in auto_results
            if result.applied
        }
        
        if status == 'resolved':
            return [g for g in groups if g.base_name in auto_resolved_groups]
        elif status == 'unresolved':
            return [g for g in groups if g.base_name not in auto_resolved_groups]
        else:
            return groups
    
    @staticmethod
    def get_unresolved_count(
        groups: List[DuplicateGroup],
        auto_results: List[AutoSelectionResult]
    ) -> int:
        """
        Get count of unresolved groups.
        
        Args:
            groups: All duplicate groups
            auto_results: Auto-selection results
            
        Returns:
            Number of unresolved groups
        """
        unresolved = GroupFilter.filter_by_resolution_status(
            groups, auto_results, 'unresolved'
        )
        return len(unresolved)