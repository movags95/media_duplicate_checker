"""Visual similarity analysis for media files."""

import logging
from pathlib import Path
from typing import Optional

import imagehash
from PIL import Image

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

from .models import FileMetadata

logger = logging.getLogger(__name__)


class SimilarityAnalyzer:
    """Analyzes visual similarity between media files."""
    
    def __init__(self, image_threshold: float = 0.90, video_threshold: float = 0.85):
        """
        Initialize the similarity analyzer.
        
        Args:
            image_threshold: Similarity threshold for images (0.0-1.0)
            video_threshold: Similarity threshold for videos (0.0-1.0)
        """
        self.image_threshold = image_threshold
        self.video_threshold = video_threshold
        
    def calculate_similarity(self, file1: FileMetadata, file2: FileMetadata) -> float:
        """
        Calculate similarity score between two media files.
        
        Args:
            file1: First file to compare
            file2: Second file to compare
            
        Returns:
            Similarity score between 0.0 (completely different) and 1.0 (identical)
            
        Raises:
            ValueError: If files cannot be compared or are of different types
        """
        if not file1.file_path.exists() or not file2.file_path.exists():
            raise ValueError("One or both files do not exist")
            
        ext1 = file1.extension.lower()
        ext2 = file2.extension.lower()
        
        # Files must be same type for comparison
        if self._get_media_type(ext1) != self._get_media_type(ext2):
            raise ValueError("Cannot compare files of different media types")
            
        media_type = self._get_media_type(ext1)
        
        if media_type == "image":
            return self._calculate_image_similarity(file1, file2)
        elif media_type == "video":
            return self._calculate_video_similarity(file1, file2)
        else:
            raise ValueError(f"Unsupported media type for comparison: {media_type}")
    
    def are_visually_similar(self, file1: FileMetadata, file2: FileMetadata) -> bool:
        """
        Check if two files are visually similar based on configured thresholds.
        
        Args:
            file1: First file to compare
            file2: Second file to compare
            
        Returns:
            True if files are visually similar, False otherwise
        """
        try:
            similarity = self.calculate_similarity(file1, file2)
            media_type = self._get_media_type(file1.extension.lower())
            
            if media_type == "image":
                return similarity >= self.image_threshold
            elif media_type == "video":
                return similarity >= self.video_threshold
            return False
            
        except (ValueError, Exception) as e:
            logger.warning(f"Could not compare {file1.filename} and {file2.filename}: {e}")
            return False
    
    def _get_media_type(self, extension: str) -> str:
        """Get media type from file extension."""
        image_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", 
            ".webp", ".ico", ".heic", ".heif"
        }
        video_extensions = {
            ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"
        }
        
        if extension in image_extensions:
            return "image"
        elif extension in video_extensions:
            return "video"
        else:
            return "unknown"
    
    def _calculate_image_similarity(self, file1: FileMetadata, file2: FileMetadata) -> float:
        """
        Calculate similarity between two image files using perceptual hashing.
        
        Args:
            file1: First image file
            file2: Second image file
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Generate perceptual hashes for both images
            hash1 = self._get_image_hash(file1.file_path)
            hash2 = self._get_image_hash(file2.file_path)
            
            if hash1 is None or hash2 is None:
                return 0.0
            
            # Calculate Hamming distance between hashes
            hamming_distance = hash1 - hash2
            
            # Convert to similarity score (0-1 scale)
            # Hash size is typically 64 bits, so max distance is 64
            max_distance = len(str(hash1)) * 4  # Each hex char represents 4 bits
            similarity = max(0.0, 1.0 - (hamming_distance / max_distance))
            
            logger.debug(
                f"Image similarity between {file1.filename} and {file2.filename}: "
                f"{similarity:.3f} (distance: {hamming_distance})"
            )
            
            return similarity
            
        except Exception as e:
            logger.warning(f"Error calculating image similarity: {e}")
            return 0.0
    
    def _get_image_hash(self, image_path: Path) -> Optional[imagehash.ImageHash]:
        """
        Generate perceptual hash for an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            ImageHash object or None if generation failed
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                
                # Use difference hash (dHash) as it's good for detecting similar images
                # even with slight modifications like resizing or compression
                return imagehash.dhash(img, hash_size=8)
                
        except Exception as e:
            logger.debug(f"Could not generate hash for {image_path}: {e}")
            return None
    
    def _calculate_video_similarity(self, file1: FileMetadata, file2: FileMetadata) -> float:
        """
        Calculate similarity between two video files based on metadata.
        
        For now, this uses file size and duration as similarity indicators.
        Future enhancement could include frame sampling and comparison.
        
        Args:
            file1: First video file
            file2: Second video file
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # For basic video comparison, use file size similarity
            # This is a simple approach that works well for identifying
            # files that are likely the same content in different formats
            
            size1 = file1.size_bytes
            size2 = file2.size_bytes
            
            if size1 == 0 or size2 == 0:
                return 0.0
            
            # Calculate size similarity ratio
            size_ratio = min(size1, size2) / max(size1, size2)
            
            # For videos, size similarity is a strong indicator
            # Boost similarity if sizes are very close (within 5%)
            if size_ratio >= 0.95:
                similarity = 0.9 + (size_ratio - 0.95) * 2  # Scale 0.95-1.0 to 0.9-1.0
            else:
                similarity = size_ratio * 0.9  # Scale proportionally
            
            logger.debug(
                f"Video similarity between {file1.filename} and {file2.filename}: "
                f"{similarity:.3f} (size ratio: {size_ratio:.3f})"
            )
            
            return min(similarity, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating video similarity: {e}")
            return 0.0


class SuffixDetector:
    """Detects numeric suffixes in filenames that indicate copies or duplicates."""
    
    def __init__(self):
        """Initialize the suffix detector."""
        self.suffix_patterns = [
            r"_(\d+)$",           # filename_1, filename_2
            r"\s*\((\d+)\)$",     # filename (1), filename (2)
            r"\s*-\s*(\d+)$",     # filename - 1, filename - 2
            r"\s+(\d+)$",         # filename 1, filename 2
            r"_copy(\d*)$",       # filename_copy, filename_copy2
            r"\s+copy(\d*)$",     # filename copy, filename copy2
        ]
    
    def has_numeric_suffix(self, filename: str) -> bool:
        """
        Check if filename has a numeric suffix indicating it's a copy.
        
        Args:
            filename: Filename to check (without extension)
            
        Returns:
            True if filename has a numeric suffix, False otherwise
        """
        import re
        
        # Remove extension for analysis
        name_without_ext = Path(filename).stem.lower()
        
        for pattern in self.suffix_patterns:
            if re.search(pattern, name_without_ext):
                return True
        
        return False
    
    def get_suffix_priority(self, filename: str) -> int:
        """
        Get priority score for filename based on suffix.
        Lower scores indicate higher priority (should be kept).
        
        Args:
            filename: Filename to analyze
            
        Returns:
            Priority score (0 = original, higher = more likely to be copy)
        """
        import re
        
        name_without_ext = Path(filename).stem.lower()
        
        # Check each pattern and return priority based on suffix number
        for pattern in self.suffix_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                # Extract number from suffix
                number_str = match.group(1) if match.group(1) else "1"
                try:
                    number = int(number_str) if number_str else 1
                    return number  # Higher numbers = lower priority
                except ValueError:
                    return 1
        
        return 0  # No suffix = highest priority (original file)
    
    def identify_original(self, files: list[FileMetadata]) -> Optional[FileMetadata]:
        """
        Identify the original file from a list based on suffix analysis.
        
        Args:
            files: List of files to analyze
            
        Returns:
            The file most likely to be the original, or None if cannot determine
        """
        if not files:
            return None
        
        if len(files) == 1:
            return files[0]
        
        # Calculate priority for each file
        file_priorities = []
        for file in files:
            priority = self.get_suffix_priority(file.filename)
            file_priorities.append((file, priority))
        
        # Sort by priority (lower = better)
        file_priorities.sort(key=lambda x: x[1])
        
        # Return the file with highest priority (lowest score)
        return file_priorities[0][0]