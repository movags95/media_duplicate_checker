"""Duplicate review window for examining and managing duplicate groups."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..core import DuplicateGroup, FileMetadata, ScanResult

logger = logging.getLogger(__name__)


class DuplicateReviewWindow:
    """Window for reviewing and managing duplicate file groups."""

    def __init__(self, parent: tk.Tk, scan_result: ScanResult):
        """
        Initialize the duplicate review window.

        Args:
            parent: Parent tkinter window
            scan_result: Results from the duplicate scan
        """
        self.parent = parent
        self.scan_result = scan_result

        # State tracking
        self.files_to_delete: set[Path] = set()
        self.current_group_index = 0

        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("Review Duplicate Groups")
        self.window.geometry("1000x700")
        self.window.minsize(800, 600)

        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()

        self._setup_gui()
        self._load_first_group()

    def _setup_gui(self) -> None:
        """Set up the GUI components."""
        # Configure grid weights
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_columnconfigure(0, weight=1)

        self._create_header()
        self._create_main_content()
        self._create_footer()

    def _create_header(self) -> None:
        """Create the header with navigation and summary."""
        header_frame = ttk.Frame(self.window, padding="10")
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # Navigation controls
        nav_frame = ttk.Frame(header_frame)
        nav_frame.grid(row=0, column=0, sticky="w")

        self.prev_button = ttk.Button(nav_frame, text="◀ Previous", command=self._prev_group)
        self.prev_button.grid(row=0, column=0, padx=(0, 5))

        self.next_button = ttk.Button(nav_frame, text="Next ▶", command=self._next_group)
        self.next_button.grid(row=0, column=1)

        # Summary info
        self.summary_label = ttk.Label(header_frame, text="", font=("Arial", 11, "bold"))
        self.summary_label.grid(row=0, column=1)

        # Current group info
        self.group_info_label = ttk.Label(header_frame, text="", font=("Arial", 10))
        self.group_info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

    def _create_main_content(self) -> None:
        """Create the main content area with file comparison."""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=1, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Create notebook for different views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # File comparison tab
        self.comparison_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.comparison_frame, text="File Comparison")
        self._setup_comparison_view()

        # Details tab
        self.details_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.details_frame, text="Detailed View")
        self._setup_details_view()

    def _setup_comparison_view(self) -> None:
        """Set up the side-by-side file comparison view."""
        self.comparison_frame.grid_rowconfigure(0, weight=1)
        self.comparison_frame.grid_columnconfigure(0, weight=1)

        # Scrollable frame for file cards
        canvas = tk.Canvas(self.comparison_frame)
        scrollbar = ttk.Scrollbar(self.comparison_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Store reference to canvas for scrolling
        self.canvas = canvas

    def _setup_details_view(self) -> None:
        """Set up the detailed tree view."""
        self.details_frame.grid_rowconfigure(0, weight=1)
        self.details_frame.grid_columnconfigure(0, weight=1)

        # Create treeview with scrollbars
        tree_frame = ttk.Frame(self.details_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        columns = ("filename", "size", "created", "modified", "action")
        self.details_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")

        # Configure columns
        self.details_tree.heading("#0", text="Path")
        self.details_tree.heading("filename", text="Filename")
        self.details_tree.heading("size", text="Size (MB)")
        self.details_tree.heading("created", text="Created")
        self.details_tree.heading("modified", text="Modified")
        self.details_tree.heading("action", text="Action")

        self.details_tree.column("#0", width=200, minwidth=150)
        self.details_tree.column("filename", width=200, minwidth=150)
        self.details_tree.column("size", width=80, minwidth=80)
        self.details_tree.column("created", width=120, minwidth=120)
        self.details_tree.column("modified", width=120, minwidth=120)
        self.details_tree.column("action", width=80, minwidth=80)

        # Scrollbars for tree
        tree_v_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.details_tree.yview
        )
        tree_h_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.details_tree.xview
        )
        self.details_tree.configure(
            yscrollcommand=tree_v_scroll.set, xscrollcommand=tree_h_scroll.set
        )

        self.details_tree.grid(row=0, column=0, sticky="nsew")
        tree_v_scroll.grid(row=0, column=1, sticky="ns")
        tree_h_scroll.grid(row=1, column=0, sticky="ew")

    def _create_footer(self) -> None:
        """Create the footer with action buttons."""
        footer_frame = ttk.Frame(self.window, padding="10")
        footer_frame.grid(row=2, column=0, sticky="ew")

        # Action buttons
        button_frame = ttk.Frame(footer_frame)
        button_frame.grid(row=0, column=0)

        ttk.Button(
            button_frame,
            text="Mark All Smaller Files for Deletion",
            command=self._mark_smaller_files,
        ).grid(row=0, column=0, padx=(0, 10))

        ttk.Button(
            button_frame, text="Mark All Older Files for Deletion", command=self._mark_older_files
        ).grid(row=0, column=1, padx=(0, 10))

        ttk.Button(button_frame, text="Clear All Selections", command=self._clear_selections).grid(
            row=0, column=2, padx=(0, 20)
        )

        # Close button
        ttk.Button(footer_frame, text="Close", command=self._close).grid(
            row=0, column=1, sticky="e"
        )
        footer_frame.grid_columnconfigure(0, weight=1)

        # Selection summary
        self.selection_label = ttk.Label(footer_frame, text="No files selected for deletion")
        self.selection_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

    def _load_first_group(self) -> None:
        """Load the first duplicate group."""
        if self.scan_result.duplicate_groups:
            self.current_group_index = 0
            self._load_current_group()
        else:
            self.summary_label.config(text="No duplicate groups found")

    def _load_current_group(self) -> None:
        """Load and display the current duplicate group."""
        if not self.scan_result.duplicate_groups:
            return

        group = self.scan_result.duplicate_groups[self.current_group_index]

        # Update header
        self.summary_label.config(
            text=f"Group {self.current_group_index + 1} of {len(self.scan_result.duplicate_groups)}"
        )
        self.group_info_label.config(
            text=f"Base name: '{group.base_name}' | {group.file_count} files | "
            f"{group.total_size_mb:.1f} MB | Confidence: {group.confidence_score:.0%}"
        )

        # Update navigation buttons
        self.prev_button.config(state="normal" if self.current_group_index > 0 else "disabled")
        self.next_button.config(
            state="normal"
            if self.current_group_index < len(self.scan_result.duplicate_groups) - 1
            else "disabled"
        )

        # Load file cards
        self._load_file_comparison(group)
        self._load_file_details(group)
        self._update_selection_summary()

    def _load_file_comparison(self, group: DuplicateGroup) -> None:
        """Load files into the comparison view."""
        # Clear existing cards
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Create file cards
        for i, file in enumerate(group.files):
            self._create_file_card(file, i)

    def _create_file_card(self, file: FileMetadata, index: int) -> None:
        """Create a file comparison card."""
        # Card frame
        card_frame = ttk.LabelFrame(self.scrollable_frame, text=f"File {index + 1}", padding="10")
        card_frame.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=5)

        # File info
        ttk.Label(card_frame, text="Filename:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(card_frame, text=file.filename, wraplength=250).grid(
            row=0, column=1, sticky="w", padx=(5, 0)
        )

        ttk.Label(card_frame, text="Size:", font=("Arial", 9, "bold")).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Label(card_frame, text=f"{file.size_mb:.1f} MB").grid(
            row=1, column=1, sticky="w", padx=(5, 0)
        )

        ttk.Label(card_frame, text="Created:", font=("Arial", 9, "bold")).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(card_frame, text=file.created_at.strftime("%Y-%m-%d %H:%M")).grid(
            row=2, column=1, sticky="w", padx=(5, 0)
        )

        ttk.Label(card_frame, text="Modified:", font=("Arial", 9, "bold")).grid(
            row=3, column=0, sticky="w"
        )
        ttk.Label(card_frame, text=file.modified_at.strftime("%Y-%m-%d %H:%M")).grid(
            row=3, column=1, sticky="w", padx=(5, 0)
        )

        ttk.Label(card_frame, text="Path:", font=("Arial", 9, "bold")).grid(
            row=4, column=0, sticky="w"
        )
        path_label = ttk.Label(card_frame, text=str(file.file_path.parent), wraplength=250)
        path_label.grid(row=4, column=1, sticky="w", padx=(5, 0))

        # Action checkbox
        delete_var = tk.BooleanVar(value=file.file_path in self.files_to_delete)
        delete_checkbox = ttk.Checkbutton(
            card_frame,
            text="Mark for deletion",
            variable=delete_var,
            command=lambda f=file, v=delete_var: self._toggle_file_deletion(f, v),
        )
        delete_checkbox.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _load_file_details(self, group: DuplicateGroup) -> None:
        """Load files into the details tree view."""
        # Clear existing items
        for item in self.details_tree.get_children():
            self.details_tree.delete(item)

        # Add files to tree
        for file in group.files:
            action = "DELETE" if file.file_path in self.files_to_delete else "KEEP"

            item_id = self.details_tree.insert(
                "",
                "end",
                text=str(file.file_path.parent),
                values=(
                    file.filename,
                    f"{file.size_mb:.1f}",
                    file.created_at.strftime("%Y-%m-%d %H:%M"),
                    file.modified_at.strftime("%Y-%m-%d %H:%M"),
                    action,
                ),
                tags=(action.lower(),),
            )

        # Configure tags for visual feedback
        self.details_tree.tag_configure("delete", foreground="red")
        self.details_tree.tag_configure("keep", foreground="black")

    def _toggle_file_deletion(self, file: FileMetadata, var: tk.BooleanVar) -> None:
        """Toggle whether a file is marked for deletion."""
        if var.get():
            self.files_to_delete.add(file.file_path)
        else:
            self.files_to_delete.discard(file.file_path)

        self._update_selection_summary()

        # Refresh the current view
        if self.scan_result.duplicate_groups:
            self._load_file_details(self.scan_result.duplicate_groups[self.current_group_index])

    def _mark_smaller_files(self) -> None:
        """Mark all smaller files in the current group for deletion."""
        if not self.scan_result.duplicate_groups:
            return

        group = self.scan_result.duplicate_groups[self.current_group_index]
        if not group.files:
            return

        # Find the largest file
        largest_file = max(group.files, key=lambda f: f.size_bytes)

        # Mark all other files for deletion
        for file in group.files:
            if file != largest_file:
                self.files_to_delete.add(file.file_path)

        self._refresh_current_group()

    def _mark_older_files(self) -> None:
        """Mark all older files in the current group for deletion."""
        if not self.scan_result.duplicate_groups:
            return

        group = self.scan_result.duplicate_groups[self.current_group_index]
        if not group.files:
            return

        # Find the newest file
        newest_file = max(group.files, key=lambda f: f.created_at)

        # Mark all other files for deletion
        for file in group.files:
            if file != newest_file:
                self.files_to_delete.add(file.file_path)

        self._refresh_current_group()

    def _clear_selections(self) -> None:
        """Clear all deletion selections for the current group."""
        if not self.scan_result.duplicate_groups:
            return

        group = self.scan_result.duplicate_groups[self.current_group_index]

        # Remove all files in this group from deletion set
        for file in group.files:
            self.files_to_delete.discard(file.file_path)

        self._refresh_current_group()

    def _refresh_current_group(self) -> None:
        """Refresh the display of the current group."""
        self._load_current_group()

    def _prev_group(self) -> None:
        """Navigate to the previous duplicate group."""
        if self.current_group_index > 0:
            self.current_group_index -= 1
            self._load_current_group()

    def _next_group(self) -> None:
        """Navigate to the next duplicate group."""
        if self.current_group_index < len(self.scan_result.duplicate_groups) - 1:
            self.current_group_index += 1
            self._load_current_group()

    def _update_selection_summary(self) -> None:
        """Update the selection summary label."""
        count = len(self.files_to_delete)
        if count == 0:
            self.selection_label.config(text="No files selected for deletion")
        elif count == 1:
            self.selection_label.config(text="1 file selected for deletion")
        else:
            self.selection_label.config(text=f"{count} files selected for deletion")

    def _close(self) -> None:
        """Close the review window."""
        if self.files_to_delete:
            result = messagebox.askyesnocancel(
                "Files Selected",
                f"You have {len(self.files_to_delete)} files marked for deletion.\n\n"
                "Do you want to delete them now?\n"
                "• Yes: Delete the selected files\n"
                "• No: Close without deleting\n"
                "• Cancel: Return to review",
            )

            if result is None:  # Cancel
                return
            if result:  # Yes - delete files
                self._delete_selected_files()

        self.window.destroy()

    def _delete_selected_files(self) -> None:
        """Delete the selected files (placeholder implementation)."""
        # For safety, we'll just show what would be deleted
        # In a real implementation, this would actually delete files
        if not self.files_to_delete:
            return

        file_list = "\n".join(str(path) for path in self.files_to_delete)
        messagebox.showinfo(
            "Files Would Be Deleted",
            f"The following {len(self.files_to_delete)} files would be deleted:\n\n{file_list}\n\n"
            "Note: Actual deletion is not implemented for safety reasons.",
        )

    def show(self) -> None:
        """Show the review window."""
        self.window.focus_set()
        self.window.wait_window()
