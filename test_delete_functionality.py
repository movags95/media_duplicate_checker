#!/usr/bin/env python3
"""Test script to manually verify delete functionality."""

import tempfile
import tkinter as tk
from pathlib import Path
from datetime import datetime

from src.media_duplicate_checker.core import DuplicateGroup, FileMetadata, ScanResult
from src.media_duplicate_checker.ui.review_window import DuplicateReviewWindow


def create_test_files():
    """Create temporary test files."""
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Creating test files in: {temp_dir}")
    
    test_files = []
    for i in range(3):
        file_path = temp_dir / f"duplicate_image_{i}.jpg"
        # Create a simple test image file
        with open(file_path, 'w') as f:
            f.write(f"fake image content {i}")
        test_files.append(file_path)
        print(f"Created: {file_path}")
    
    return test_files


def create_scan_result(test_files):
    """Create a scan result with duplicate files."""
    file_metadata = []
    for i, file_path in enumerate(test_files):
        stat_info = file_path.stat()
        metadata = FileMetadata(
            file_path=file_path,
            filename=file_path.name,
            size_bytes=stat_info.st_size,
            created_at=datetime.fromtimestamp(stat_info.st_ctime),
            modified_at=datetime.fromtimestamp(stat_info.st_mtime)
        )
        file_metadata.append(metadata)
    
    # Create duplicate group
    group = DuplicateGroup(
        base_name="duplicate_image",
        pattern_type="IMG",
        files=file_metadata,
        confidence_score=0.95
    )
    
    # Create scan result
    scan_result = ScanResult(
        scan_path=test_files[0].parent,
        total_files_found=len(test_files),
        media_files_found=len(test_files),
        duplicate_groups=[group],
        scan_duration_seconds=1.0
    )
    
    return scan_result


def main():
    """Run the delete functionality test."""
    print("🧪 Testing Delete Functionality")
    print("=" * 50)
    
    # Create test files
    test_files = create_test_files()
    
    # Verify files exist
    print(f"\n📁 Created {len(test_files)} test files:")
    for f in test_files:
        print(f"  ✓ {f} ({f.stat().st_size} bytes)")
    
    # Create scan result
    scan_result = create_scan_result(test_files)
    print(f"\n📊 Created scan result with {len(scan_result.duplicate_groups)} duplicate group(s)")
    
    # Create and show review window
    print("\n🖥️  Opening review window...")
    print("Instructions:")
    print("  1. Select one or more files for deletion using the checkboxes")
    print("  2. Click the '🗑️ Delete Selected Files' button")
    print("  3. Confirm the deletion in the dialog")
    print("  4. Verify files are actually deleted from the filesystem")
    print("  5. Close the window when done")
    
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        review_window = DuplicateReviewWindow(root, scan_result)
        review_window.show()  # This will block until window is closed
        
    except Exception as e:
        print(f"❌ Error opening review window: {e}")
        return
    
    # Check which files still exist
    print(f"\n📋 Post-deletion file status:")
    remaining_files = []
    deleted_files = []
    
    for f in test_files:
        if f.exists():
            remaining_files.append(f)
            print(f"  📄 Still exists: {f}")
        else:
            deleted_files.append(f)
            print(f"  🗑️  Deleted: {f}")
    
    print(f"\n📈 Summary:")
    print(f"  • Files deleted: {len(deleted_files)}")
    print(f"  • Files remaining: {len(remaining_files)}")
    
    # Cleanup remaining files
    if remaining_files:
        print(f"\n🧹 Cleaning up remaining test files...")
        for f in remaining_files:
            try:
                f.unlink()
                print(f"  ✓ Cleaned up: {f}")
            except Exception as e:
                print(f"  ❌ Could not clean up {f}: {e}")
    
    # Remove temp directory if empty
    try:
        temp_dir = test_files[0].parent
        if not list(temp_dir.iterdir()):
            temp_dir.rmdir()
            print(f"  ✓ Removed empty directory: {temp_dir}")
    except Exception as e:
        print(f"  ❌ Could not remove directory: {e}")
    
    print("\n✅ Delete functionality test completed!")


if __name__ == "__main__":
    main()