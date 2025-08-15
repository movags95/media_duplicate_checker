"""Main application window using tkinter."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..core import ApplicationConfig, DuplicateGrouper, MediaFileScanner, ScanResult
from .review_window import DuplicateReviewWindow

logger = logging.getLogger(__name__)


class MainWindow:
    """Main application window for media duplicate checker."""

    def __init__(self):
        """Initialize the main window."""
        self.root = tk.Tk()
        self.root.title("Media Duplicate Checker")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # Application components
        self.config = ApplicationConfig()
        self.scanner = MediaFileScanner(self.config)
        self.grouper = DuplicateGrouper(self.config)

        # State
        self.current_scan_result: ScanResult | None = None
        self.scan_in_progress = False

        # Setup GUI
        self._setup_gui()
        self._setup_bindings()

    def _setup_gui(self) -> None:
        """Set up the GUI components."""
        # Configure root grid weights
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Create main sections
        self._create_header()
        self._create_main_content()
        self._create_status_bar()

    def _create_header(self) -> None:
        """Create the header section with title and controls."""
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.grid(row=0, column=0, sticky="ew")

        # Title
        title_label = ttk.Label(
            header_frame, text="Media Duplicate Checker", font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Directory selection
        ttk.Label(header_frame, text="Select Directory:").grid(row=1, column=0, sticky="w")

        dir_frame = ttk.Frame(header_frame)
        dir_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        dir_frame.grid_columnconfigure(0, weight=1)

        self.directory_var = tk.StringVar()
        self.directory_entry = ttk.Entry(
            dir_frame, textvariable=self.directory_var, state="readonly"
        )
        self.directory_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.browse_button = ttk.Button(dir_frame, text="Browse...", command=self._browse_directory)
        self.browse_button.grid(row=0, column=1)

        # Action buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(15, 0))

        self.scan_button = ttk.Button(
            button_frame,
            text="Scan for Duplicates",
            command=self._start_scan,
            style="Accent.TButton",
        )
        self.scan_button.grid(row=0, column=0, padx=(0, 10))

        self.review_button = ttk.Button(
            button_frame, text="Review Last Scan", command=self._review_scan, state="disabled"
        )
        self.review_button.grid(row=0, column=1)

    def _create_main_content(self) -> None:
        """Create the main content area."""
        # Main content frame
        content_frame = ttk.Frame(self.root, padding="10")
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.grid_rowconfigure(1, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # Info label
        self.info_label = ttk.Label(
            content_frame,
            text="Select a directory and click 'Scan for Duplicates' to get started.",
            font=("Arial", 11),
        )
        self.info_label.grid(row=0, column=0, pady=(0, 10))

        # Progress frame (initially hidden)
        self.progress_frame = ttk.Frame(content_frame)
        self.progress_frame.grid(row=1, column=0, sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.progress_bar = ttk.Progressbar(
            self.progress_frame, mode="indeterminate", style="TProgressbar"
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew")

        # Results frame
        self.results_frame = ttk.LabelFrame(content_frame, text="Scan Results", padding="10")
        self.results_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.results_frame.grid_columnconfigure(1, weight=1)

        # Initially hide progress and results
        self.progress_frame.grid_remove()
        self.results_frame.grid_remove()

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self.status_bar = ttk.Frame(self.root, relief="sunken", padding="5")
        self.status_bar.grid(row=2, column=0, sticky="ew")

        self.status_label = ttk.Label(self.status_bar, text="Ready")
        self.status_label.grid(row=0, column=0, sticky="w")

    def _setup_bindings(self) -> None:
        """Set up event bindings."""
        # Allow Enter key in directory entry to start scan
        self.directory_entry.bind("<Return>", lambda e: self._start_scan())

    def _browse_directory(self) -> None:
        """Open directory selection dialog."""
        directory = filedialog.askdirectory(title="Select Directory to Scan for Duplicates")

        if directory:
            self.directory_var.set(directory)
            self._update_status(f"Selected directory: {directory}")

    def _start_scan(self) -> None:
        """Start scanning for duplicates."""
        directory_path = self.directory_var.get().strip()

        if not directory_path:
            messagebox.showwarning("No Directory", "Please select a directory to scan.")
            return

        scan_path = Path(directory_path)
        if not scan_path.exists():
            messagebox.showerror("Invalid Directory", "The selected directory does not exist.")
            return

        if not scan_path.is_dir():
            messagebox.showerror("Invalid Directory", "The selected path is not a directory.")
            return

        # Start the scan
        self._run_scan(scan_path)

    def _run_scan(self, directory: Path) -> None:
        """Run the duplicate scan operation."""
        try:
            self._show_progress("Scanning directory...")
            self.scan_in_progress = True
            self._update_scan_buttons()

            # Progress callback function
            def progress_callback(
                current: int, total: int | None = None, message: str = ""
            ) -> None:
                if message:
                    self.progress_label.config(text=message)
                self.root.update_idletasks()

            # Scan for media files
            self._update_status("Scanning for media files...")
            media_files = self.scanner.scan_directory(
                directory, recursive=True, progress_callback=progress_callback
            )

            # Group duplicates
            self._update_status("Analyzing for duplicates...")
            self.progress_label.config(text="Analyzing files for duplicates...")

            # Define progress callback for visual filtering stage
            def visual_filtering_progress_callback(
                current: int, total: int | None = None, message: str = ""
            ) -> None:
                if total:
                    percent = (current / total) * 100
                    status_msg = f"Visual analysis: {current}/{total} groups ({percent:.0f}%)"
                else:
                    status_msg = f"Visual analysis: {current} groups"

                if message:
                    self.progress_label.config(text=message)
                    self._update_status(status_msg)
                else:
                    self.progress_label.config(text=status_msg)

                self.root.update_idletasks()

            duplicate_groups = self.grouper.create_duplicate_groups(
                media_files,
                progress_callback=visual_filtering_progress_callback
                if self.config.enable_visual_filtering
                else None,
            )

            # Create scan result
            import time

            scan_duration = time.time()  # This would need to be calculated properly

            self.current_scan_result = ScanResult(
                scan_path=directory,
                total_files_found=len(media_files),  # Simplified
                media_files_found=len(media_files),
                duplicate_groups=duplicate_groups,
                scan_duration_seconds=1.0,  # Placeholder
            )

            self._show_scan_results()
            self._update_status(
                f"Scan complete: Found {len(duplicate_groups)} potential duplicate groups"
            )

        except Exception as e:
            logger.error(f"Error during scan: {e}")
            messagebox.showerror("Scan Error", f"An error occurred during scanning:\n{e}")
            self._update_status("Scan failed")

        finally:
            self._hide_progress()
            self.scan_in_progress = False
            self._update_scan_buttons()

    def _show_progress(self, message: str) -> None:
        """Show progress indicators."""
        self.info_label.grid_remove()
        self.results_frame.grid_remove()

        self.progress_frame.grid()
        self.progress_label.config(text=message)
        self.progress_bar.start(10)

    def _hide_progress(self) -> None:
        """Hide progress indicators."""
        self.progress_bar.stop()
        self.progress_frame.grid_remove()

    def _show_scan_results(self) -> None:
        """Display scan results in the main window."""
        if not self.current_scan_result:
            return

        self.results_frame.grid()

        # Clear existing results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        result = self.current_scan_result

        # Summary information
        ttk.Label(self.results_frame, text="Files scanned:").grid(row=0, column=0, sticky="w")
        ttk.Label(self.results_frame, text=str(result.media_files_found)).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Label(self.results_frame, text="Duplicate groups found:").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Label(self.results_frame, text=str(len(result.duplicate_groups))).grid(
            row=1, column=1, sticky="w"
        )

        ttk.Label(self.results_frame, text="Potential duplicates:").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(self.results_frame, text=str(result.potential_duplicates_count)).grid(
            row=2, column=1, sticky="w"
        )

        ttk.Label(self.results_frame, text="Potential space savings:").grid(
            row=3, column=0, sticky="w"
        )
        ttk.Label(self.results_frame, text=f"{result.potential_space_savings_mb:.1f} MB").grid(
            row=3, column=1, sticky="w"
        )

        # Show visual filtering statistics if enabled
        if self.config.enable_visual_filtering and hasattr(self.grouper, "visual_filtering_stats"):
            stats = self.grouper.visual_filtering_stats
            if stats["groups_analyzed"] > 0:
                ttk.Label(self.results_frame, text="Visual filtering:").grid(
                    row=4, column=0, sticky="w"
                )
                visual_stats_text = (
                    f"Analyzed {stats['groups_analyzed']} groups, "
                    f"filtered out {stats['groups_filtered_out']}, "
                    f"{stats['visual_comparisons']} comparisons"
                )
                ttk.Label(self.results_frame, text=visual_stats_text, wraplength=400).grid(
                    row=4, column=1, sticky="w"
                )

        # Show info message
        if len(result.duplicate_groups) > 0:
            self.info_label.config(
                text=f"Found {len(result.duplicate_groups)} groups of potential duplicates. Click 'Review Last Scan' to examine them."
            )
        else:
            self.info_label.config(text="No potential duplicates found in the selected directory.")

        self.info_label.grid()

    def _review_scan(self) -> None:
        """Open the duplicate review window."""
        if not self.current_scan_result:
            messagebox.showinfo("No Scan Results", "No scan results available to review.")
            return

        try:
            review_window = DuplicateReviewWindow(self.root, self.current_scan_result, self.config)
            review_window.show()
        except Exception as e:
            logger.error(f"Error opening review window: {e}")
            messagebox.showerror("Error", f"Could not open review window:\n{e}")

    def _update_scan_buttons(self) -> None:
        """Update the state of scan-related buttons."""
        if self.scan_in_progress:
            self.scan_button.config(state="disabled")
            self.browse_button.config(state="disabled")
        else:
            self.scan_button.config(state="normal")
            self.browse_button.config(state="normal")

            # Enable review button if we have scan results
            if self.current_scan_result and len(self.current_scan_result.duplicate_groups) > 0:
                self.review_button.config(state="normal")
            else:
                self.review_button.config(state="disabled")

    def _update_status(self, message: str) -> None:
        """Update the status bar message."""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def run(self) -> None:
        """Start the GUI event loop."""
        self.root.mainloop()

    def destroy(self) -> None:
        """Clean up and destroy the window."""
        self.root.destroy()
