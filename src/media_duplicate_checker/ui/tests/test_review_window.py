"""Tests for the review window delete functionality."""

import tempfile
import tkinter as tk
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from ..review_window import DuplicateReviewWindow
from ...core import DuplicateGroup, FileMetadata, ScanResult


@pytest.fixture
def temp_test_files():
    """Create temporary test files for deletion testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        test_files = []
        for i in range(3):
            file_path = temp_path / f"test_file_{i}.jpg"
            file_path.write_text(f"test content {i}")
            test_files.append(file_path)

        yield test_files


@pytest.fixture
def sample_scan_result(temp_test_files):
    """Create a sample scan result with test files."""
    # Create file metadata for test files
    file_metadata = []
    for i, file_path in enumerate(temp_test_files):
        metadata = FileMetadata(
            file_path=file_path,
            filename=file_path.name,
            size_bytes=len(f"test content {i}"),
            created_at=datetime.now(),
            modified_at=datetime.now(),
        )
        file_metadata.append(metadata)

    # Create duplicate group
    group = DuplicateGroup(
        base_name="test_file", pattern_type="TEST", files=file_metadata, confidence_score=0.95
    )

    # Create scan result
    scan_result = ScanResult(
        scan_path=temp_test_files[0].parent,
        total_files_found=len(temp_test_files),
        media_files_found=len(temp_test_files),
        duplicate_groups=[group],
        scan_duration_seconds=1.0,
    )

    return scan_result


@pytest.fixture
def root_window():
    """Create a root tkinter window for testing."""
    root = tk.Tk()
    root.withdraw()  # Hide the window during tests
    yield root
    root.destroy()


class TestDuplicateReviewWindow:
    """Test cases for DuplicateReviewWindow delete functionality."""

    @patch("tkinter.messagebox.askyesno")
    def test_delete_selected_files_no_files_selected(
        self, mock_messagebox, root_window, sample_scan_result
    ):
        """Test delete function when no files are selected."""
        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Call delete without selecting any files
        review_window._delete_selected_files()

        # Should return early without showing any dialogs
        mock_messagebox.assert_not_called()

    @patch("tkinter.messagebox.showinfo")
    def test_delete_selected_files_missing_files(
        self, mock_showinfo, root_window, sample_scan_result
    ):
        """Test delete function when selected files don't exist."""
        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Add non-existent files to deletion set
        non_existent_file = Path("/non/existent/file.jpg")
        review_window.files_to_delete.add(non_existent_file)

        review_window._delete_selected_files()

        # Should show info about no files to delete
        mock_showinfo.assert_called_once()
        args, kwargs = mock_showinfo.call_args
        assert "No Files to Delete" in args[0]
        assert len(review_window.files_to_delete) == 0

    @patch("tkinter.messagebox.askyesno")
    def test_delete_selected_files_user_cancels(
        self, mock_messagebox, root_window, sample_scan_result, temp_test_files
    ):
        """Test delete function when user cancels confirmation."""
        mock_messagebox.return_value = False  # User clicks "No"

        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Select first file for deletion
        review_window.files_to_delete.add(temp_test_files[0])

        review_window._delete_selected_files()

        # Should ask for confirmation
        mock_messagebox.assert_called_once()

        # File should still exist
        assert temp_test_files[0].exists()
        assert temp_test_files[0] in review_window.files_to_delete

    @patch("tkinter.messagebox.askyesno")
    @patch("tkinter.messagebox.showinfo")
    @patch("os.remove")
    def test_delete_selected_files_successful_deletion(
        self,
        mock_remove,
        mock_showinfo,
        mock_messagebox,
        root_window,
        sample_scan_result,
        temp_test_files,
    ):
        """Test successful file deletion."""
        mock_messagebox.return_value = True  # User confirms deletion

        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Select first file for deletion
        file_to_delete = temp_test_files[0]
        review_window.files_to_delete.add(file_to_delete)

        review_window._delete_selected_files()

        # Should ask for confirmation
        mock_messagebox.assert_called_once()

        # Should attempt to delete the file
        mock_remove.assert_called_once_with(file_to_delete)

        # Should show success message
        mock_showinfo.assert_called_once()
        args, kwargs = mock_showinfo.call_args
        assert "Deletion Complete" in args[0]

        # File should be removed from deletion set
        assert file_to_delete not in review_window.files_to_delete

    @patch("tkinter.messagebox.askyesno")
    @patch("tkinter.messagebox.showerror")
    @patch("os.remove")
    def test_delete_selected_files_deletion_failure(
        self,
        mock_remove,
        mock_showerror,
        mock_messagebox,
        root_window,
        sample_scan_result,
        temp_test_files,
    ):
        """Test handling of file deletion failures."""
        mock_messagebox.return_value = True  # User confirms deletion
        mock_remove.side_effect = OSError("Permission denied")  # Simulate deletion failure

        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Select first file for deletion
        file_to_delete = temp_test_files[0]
        review_window.files_to_delete.add(file_to_delete)

        review_window._delete_selected_files()

        # Should ask for confirmation
        mock_messagebox.assert_called_once()

        # Should attempt to delete the file
        mock_remove.assert_called_once_with(file_to_delete)

        # Should show error message
        mock_showerror.assert_called_once()
        args, kwargs = mock_showerror.call_args
        assert "Deletion Failed" in args[0]

        # File should remain in deletion set since deletion failed
        assert file_to_delete in review_window.files_to_delete

    def test_update_selection_summary_enables_delete_button(
        self, root_window, sample_scan_result, temp_test_files
    ):
        """Test that delete button is enabled when files are selected."""
        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Initially, no files selected - button should be disabled
        assert review_window.delete_button.cget("state") == "disabled"

        # Select a file
        review_window.files_to_delete.add(temp_test_files[0])
        review_window._update_selection_summary()

        # Button should now be enabled
        assert review_window.delete_button.cget("state") == "normal"

        # Clear selection
        review_window.files_to_delete.clear()
        review_window._update_selection_summary()

        # Button should be disabled again
        assert review_window.delete_button.cget("state") == "disabled"

    @patch("tkinter.messagebox.askyesno")
    def test_close_with_selected_files_warns_user(
        self, mock_messagebox, root_window, sample_scan_result, temp_test_files
    ):
        """Test that closing with selected files warns the user."""
        mock_messagebox.return_value = False  # User chooses not to close

        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Select a file
        review_window.files_to_delete.add(temp_test_files[0])

        # Try to close
        review_window._close()

        # Should warn user about unsaved selections
        mock_messagebox.assert_called_once()
        args, kwargs = mock_messagebox.call_args
        assert "Files Selected" in args[0]
        assert "close without deleting" in args[1]

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    @patch("tkinter.messagebox.askyesno")
    @patch("tkinter.messagebox.showinfo")
    def test_delete_selected_files_macos_trash(
        self,
        mock_showinfo,
        mock_messagebox,
        mock_subprocess,
        root_window,
        sample_scan_result,
        temp_test_files,
    ):
        """Test file deletion uses trash on macOS."""
        mock_messagebox.return_value = True  # User confirms deletion
        mock_subprocess.return_value = Mock(returncode=0)  # Successful trash operation

        review_window = DuplicateReviewWindow(root_window, sample_scan_result)

        # Select first file for deletion
        file_to_delete = temp_test_files[0]
        review_window.files_to_delete.add(file_to_delete)

        review_window._delete_selected_files()

        # Should attempt to move to trash using AppleScript
        mock_subprocess.assert_called_once()
        args, kwargs = mock_subprocess.call_args
        assert "osascript" in args[0]
        assert 'tell app "Finder" to delete' in " ".join(args[0])

        # Should show success message
        mock_showinfo.assert_called_once()
