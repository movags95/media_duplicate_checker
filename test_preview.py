#!/usr/bin/env python3
"""Test script to verify the enhanced preview functionality with test photos."""

import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from media_duplicate_checker.ui.main_window import MainWindow

def main():
    """Test the preview functionality with test photos."""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the app
    app = MainWindow()
    
    # Set the test directory
    test_dir = "/Users/mohitvaghela/Desktop/testphotos"
    if Path(test_dir).exists():
        app.directory_var.set(test_dir)
        print(f"✅ Test directory set to: {test_dir}")
        print("📋 Instructions:")
        print("1. Click 'Scan for Duplicates' to analyze the test photos")
        print("2. Click 'Review Last Scan' to see the enhanced preview functionality")
        print("3. Look for:")
        print("   - Enhanced thumbnails (150x150px with better styling)")
        print("   - Image dimensions displayed under thumbnails")
        print("   - HEIC file support (if pillow-heif is working)")
        print("   - File type placeholders for unsupported formats")
        print("   - Enhanced file information (format, detailed timestamps)")
        print("   - Visual feedback for marked files (🗑️ and ✅ icons)")
        print("   - 'Open Location' button functionality")
        print("")
        print("🚀 Starting GUI...")
    else:
        print(f"❌ Test directory not found: {test_dir}")
        print("Please make sure the test photos are in the correct location")
        return
    
    # Run the app
    app.run()

if __name__ == "__main__":
    main()