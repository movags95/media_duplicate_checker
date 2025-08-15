"""Duplicate review window for examining and managing duplicate groups."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

try:
    import pillow_heif

    # Register HEIF opener with Pillow
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

from ..core import ApplicationConfig, DuplicateGroup, FileMetadata, ScanResult
from ..core.auto_selector import AutoSelector, AutoSelectionResult, GroupFilter

logger = logging.getLogger(__name__)


class DuplicateReviewWindow:
    """Window for reviewing and managing duplicate file groups."""

    def __init__(self, parent: tk.Tk, scan_result: ScanResult, config: ApplicationConfig | None = None):
        """
        Initialize the duplicate review window.

        Args:
            parent: Parent tkinter window
            scan_result: Results from the duplicate scan
            config: Application configuration (optional)
        """
        self.parent = parent
        self.scan_result = scan_result
        self.config = config or ApplicationConfig()

        # State tracking
        self.files_to_delete: set[Path] = set()
        self.current_group_index = 0
        
        # Auto-selection components
        self.auto_selector = AutoSelector(
            image_similarity_threshold=self.config.image_similarity_threshold,
            video_similarity_threshold=self.config.video_similarity_threshold,
            min_confidence_threshold=self.config.auto_selection_confidence_threshold
        )
        self.auto_results: list[AutoSelectionResult] = []
        self.filter_status = "all"  # "all", "resolved", "unresolved"
        self.filtered_groups: list[DuplicateGroup] = []

        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("Review Duplicate Groups")
        self.window.geometry("1000x700")
        self.window.minsize(800, 600)

        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()

        # Set up keyboard shortcuts
        self._setup_keyboard_shortcuts()

        self._setup_gui()
        self._load_first_group()

    def _setup_keyboard_shortcuts(self) -> None:
        """Set up keyboard shortcuts for faster navigation."""
        # Navigation shortcuts
        self.window.bind("<Left>", lambda e: self._prev_group())
        self.window.bind("<Right>", lambda e: self._next_group())
        self.window.bind("<Prior>", lambda e: self._prev_group())  # Page Up
        self.window.bind("<Next>", lambda e: self._next_group())   # Page Down

        # File selection shortcuts (1-9 to toggle files)
        for i in range(1, 10):
            self.window.bind(f"<Key-{i}>", lambda e, idx=i-1: self._toggle_file_by_index(idx))

        # Quick action shortcuts
        self.window.bind("<s>", lambda e: self._mark_smaller_files())  # S for smaller
        self.window.bind("<S>", lambda e: self._mark_smaller_files())
        self.window.bind("<o>", lambda e: self._mark_older_files())    # O for older
        self.window.bind("<O>", lambda e: self._mark_older_files())
        self.window.bind("<c>", lambda e: self._clear_selections())    # C for clear
        self.window.bind("<C>", lambda e: self._clear_selections())
        self.window.bind("<Delete>", lambda e: self._delete_selected_files())
        self.window.bind("<BackSpace>", lambda e: self._delete_selected_files())

        # Allow focusing window to capture key events
        self.window.focus_set()

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

        # Navigation controls with larger, more accessible buttons
        nav_frame = ttk.Frame(header_frame)
        nav_frame.grid(row=0, column=0, sticky="w")

        # Style the navigation buttons for better visibility
        style = ttk.Style()
        style.configure("Large.TButton", font=("Arial", 12, "bold"))

        self.prev_button = ttk.Button(
            nav_frame,
            text="◀◀ Previous Group [←]",
            command=self._prev_group,
            style="Large.TButton",
            width=20
        )
        self.prev_button.grid(row=0, column=0, padx=(0, 10))

        self.next_button = ttk.Button(
            nav_frame,
            text="Next Group [→] ▶▶",
            command=self._next_group,
            style="Large.TButton",
            width=20
        )
        self.next_button.grid(row=0, column=1)

        # Summary info
        self.summary_label = ttk.Label(header_frame, text="", font=("Arial", 11, "bold"))
        self.summary_label.grid(row=0, column=1)

        # Current group info
        self.group_info_label = ttk.Label(header_frame, text="", font=("Arial", 10))
        self.group_info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        # Keyboard shortcuts help
        shortcuts_text = "Shortcuts: ← → (Navigate) | 1-9 (Toggle files) | S (Smaller) | O (Older) | C (Clear) | Del (Delete)"
        shortcuts_label = ttk.Label(header_frame, text=shortcuts_text, font=("Arial", 8), foreground="gray")
        shortcuts_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

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

        # Filter controls
        filter_frame = ttk.LabelFrame(footer_frame, text="Filter Groups", padding="5")
        filter_frame.grid(row=0, column=0, sticky="w", padx=(0, 20))
        
        self.filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(filter_frame, text="All", variable=self.filter_var, value="all", command=self._apply_filter).grid(row=0, column=0)
        ttk.Radiobutton(filter_frame, text="Unresolved", variable=self.filter_var, value="unresolved", command=self._apply_filter).grid(row=0, column=1)
        ttk.Radiobutton(filter_frame, text="Auto-resolved", variable=self.filter_var, value="resolved", command=self._apply_filter).grid(row=0, column=2)

        # Auto-selection controls
        auto_frame = ttk.LabelFrame(footer_frame, text="Auto Selection", padding="5")
        auto_frame.grid(row=0, column=1, sticky="w", padx=(0, 20))
        
        ttk.Button(
            auto_frame,
            text="⚡ Auto-Select Current",
            command=self._auto_select_current,
            width=18
        ).grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(
            auto_frame,
            text="⚡ Auto-Select All",
            command=self._auto_select_all,
            width=18
        ).grid(row=0, column=1)

        # Action buttons with keyboard shortcuts indicated
        button_frame = ttk.Frame(footer_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        # Configure button style
        style = ttk.Style()
        style.configure("Action.TButton", font=("Arial", 10, "bold"))

        ttk.Button(
            button_frame,
            text="Mark Smaller Files [S]",
            command=self._mark_smaller_files,
            style="Action.TButton",
            width=18
        ).grid(row=0, column=0, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Mark Older Files [O]",
            command=self._mark_older_files,
            style="Action.TButton",
            width=18
        ).grid(row=0, column=1, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Clear Selections [C]",
            command=self._clear_selections,
            style="Action.TButton",
            width=18
        ).grid(row=0, column=2, padx=(0, 20))

        # Delete selected files button
        self.delete_button = ttk.Button(
            button_frame,
            text="🗑️ Delete Selected [Del]",
            command=self._delete_selected_files,
            state="disabled",
            style="Action.TButton",
            width=20
        )
        self.delete_button.grid(row=0, column=3, padx=(0, 20))

        # Close button
        ttk.Button(footer_frame, text="Close", command=self._close).grid(
            row=0, column=2, sticky="e"
        )
        footer_frame.grid_columnconfigure(1, weight=1)

        # Selection summary
        self.selection_label = ttk.Label(footer_frame, text="No files selected for deletion")
        self.selection_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(5, 0))

    def _load_first_group(self) -> None:
        """Load the first duplicate group."""
        # Initialize filtered groups
        self._update_filtered_groups()
        
        if self.filtered_groups:
            self.current_group_index = 0
            self._load_current_group()
        else:
            self.summary_label.config(text="No duplicate groups found")

    def _load_current_group(self) -> None:
        """Load and display the current duplicate group."""
        if not self.filtered_groups:
            return

        group = self.filtered_groups[self.current_group_index]

        # Update header
        total_groups = len(self.scan_result.duplicate_groups)
        filtered_groups = len(self.filtered_groups)
        filter_text = f" ({self.filter_status})" if self.filter_status != "all" else ""
        
        self.summary_label.config(
            text=f"Group {self.current_group_index + 1} of {filtered_groups}{filter_text} (Total: {total_groups})"
        )
        self.group_info_label.config(
            text=f"Base name: '{group.base_name}' | {group.file_count} files | "
            f"{group.total_size_mb:.1f} MB | Confidence: {group.confidence_score:.0%}"
        )

        # Update navigation buttons
        self.prev_button.config(state="normal" if self.current_group_index > 0 else "disabled")
        self.next_button.config(
            state="normal"
            if self.current_group_index < len(self.filtered_groups) - 1
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

        # Configure grid weights for better card layout
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

        # Create file cards
        for i, file in enumerate(group.files):
            self._create_file_card(file, i)

    def _create_file_card(self, file: FileMetadata, index: int) -> None:
        """Create an enhanced file comparison card with preview."""
        # Card frame with better styling and keyboard shortcut indicator
        is_marked = file.file_path in self.files_to_delete
        card_title = f"[{index + 1}] File {index + 1} {'🗑️' if is_marked else ''}"

        card_frame = ttk.LabelFrame(self.scrollable_frame, text=card_title, padding="12")
        card_frame.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)

        # Configure card frame columns for better layout
        card_frame.grid_columnconfigure(2, weight=1)

        # Create enhanced preview thumbnail
        preview_widget = self._create_enhanced_preview(card_frame, file)
        if preview_widget:
            preview_widget.grid(row=0, column=0, rowspan=8, sticky="n", padx=(0, 15))
            info_column = 1
        else:
            info_column = 0

        # Enhanced file info with better formatting
        info_data = [
            ("Filename:", file.filename, 280),
            ("Size:", f"{file.size_mb:.1f} MB ({file.size_bytes:,} bytes)", None),
            ("Format:", file.extension.upper().lstrip(".") or "Unknown", None),
            ("Created:", file.created_at.strftime("%Y-%m-%d %H:%M:%S"), None),
            ("Modified:", file.modified_at.strftime("%Y-%m-%d %H:%M:%S"), None),
            ("Directory:", str(file.file_path.parent), 280),
        ]

        for row, (label_text, value_text, wrap_length) in enumerate(info_data):
            ttk.Label(card_frame, text=label_text, font=("Arial", 9, "bold")).grid(
                row=row, column=info_column, sticky="nw", pady=2
            )
            value_label = ttk.Label(
                card_frame, text=value_text, wraplength=wrap_length, font=("Arial", 9)
            )
            value_label.grid(row=row, column=info_column + 1, sticky="nw", padx=(10, 0), pady=2)

        # Enhanced action checkbox with visual feedback and larger click target
        delete_var = tk.BooleanVar(value=file.file_path in self.files_to_delete)
        checkbox_text = "🗑️ Mark for deletion" if not is_marked else "✅ Marked for deletion"

        # Create a frame for the larger click target
        checkbox_frame = ttk.Frame(card_frame)
        checkbox_frame.grid(row=6, column=info_column, columnspan=2, sticky="ew", pady=(15, 0))
        checkbox_frame.grid_columnconfigure(0, weight=1)

        delete_checkbox = ttk.Checkbutton(
            checkbox_frame,
            text=checkbox_text,
            variable=delete_var,
            command=lambda f=file, v=delete_var: self._toggle_file_deletion(f, v),
        )
        delete_checkbox.grid(row=0, column=0, sticky="w")

        # Make the entire card clickable for toggling
        def toggle_on_click(event):
            delete_var.set(not delete_var.get())
            self._toggle_file_deletion(file, delete_var)

        # Bind click events to card frame and its children (excluding buttons)
        card_frame.bind("<Button-1>", toggle_on_click)

        # Create buttons frame for better layout
        buttons_frame = ttk.Frame(card_frame)
        buttons_frame.grid(row=7, column=info_column, columnspan=2, sticky="ew", pady=(5, 0))

        # Add "Open File Location" button with improved styling
        open_button = ttk.Button(
            buttons_frame,
            text="📁 Open Location",
            command=lambda: self._open_file_location(file),
        )
        open_button.grid(row=0, column=0, sticky="w", padx=(0, 5))

        # Add quick toggle button
        toggle_button = ttk.Button(
            buttons_frame,
            text="⚡ Toggle Delete",
            command=lambda: toggle_on_click(None),
        )
        toggle_button.grid(row=0, column=1, sticky="w")

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
        if self.filtered_groups:
            self._load_file_details(self.filtered_groups[self.current_group_index])

    def _mark_smaller_files(self) -> None:
        """Mark all smaller files in the current group for deletion."""
        if not self.filtered_groups:
            return

        group = self.filtered_groups[self.current_group_index]
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
        if not self.filtered_groups:
            return

        group = self.filtered_groups[self.current_group_index]
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
        if not self.filtered_groups:
            return

        group = self.filtered_groups[self.current_group_index]

        # Remove all files in this group from deletion set
        for file in group.files:
            self.files_to_delete.discard(file.file_path)

        self._refresh_current_group()

    def _refresh_current_group(self) -> None:
        """Refresh the display of the current group."""
        self._load_current_group()

    def _toggle_file_by_index(self, index: int) -> None:
        """Toggle deletion status for file at given index using keyboard shortcut."""
        if not self.filtered_groups:
            return

        group = self.filtered_groups[self.current_group_index]
        if index < len(group.files):
            file = group.files[index]
            if file.file_path in self.files_to_delete:
                self.files_to_delete.discard(file.file_path)
            else:
                self.files_to_delete.add(file.file_path)

            self._refresh_current_group()

    def _prev_group(self) -> None:
        """Navigate to the previous duplicate group."""
        if self.current_group_index > 0:
            self.current_group_index -= 1
            self._load_current_group()

    def _next_group(self) -> None:
        """Navigate to the next duplicate group."""
        if self.current_group_index < len(self.filtered_groups) - 1:
            self.current_group_index += 1
            self._load_current_group()

    def _update_selection_summary(self) -> None:
        """Update the selection summary label and delete button state."""
        count = len(self.files_to_delete)
        if count == 0:
            self.selection_label.config(text="No files selected for deletion")
            self.delete_button.config(state="disabled")
        elif count == 1:
            self.selection_label.config(text="1 file selected for deletion")
            self.delete_button.config(state="normal")
        else:
            self.selection_label.config(text=f"{count} files selected for deletion")
            self.delete_button.config(state="normal")

    def _close(self) -> None:
        """Close the review window."""
        if self.files_to_delete:
            result = messagebox.askyesno(
                "Files Selected",
                f"You have {len(self.files_to_delete)} files marked for deletion.\n\n"
                "Are you sure you want to close without deleting them?\n"
                "Use the 'Delete Selected Files' button to delete them first.",
                icon="warning",
                default="no",
            )
            if not result:  # No - don't close
                return

        self.window.destroy()

    def _create_enhanced_preview(self, parent: ttk.Frame, file: FileMetadata) -> ttk.Frame | None:
        """Create an enhanced preview widget with image and metadata."""
        preview_frame = ttk.Frame(parent)

        # Create thumbnail
        thumbnail_label = self._create_preview_thumbnail(preview_frame, file)
        if thumbnail_label:
            thumbnail_label.grid(row=0, column=0, sticky="n")

            # Add image dimensions if available
            dimensions_text = self._get_image_dimensions(file)
            if dimensions_text:
                ttk.Label(
                    preview_frame, text=dimensions_text, font=("Arial", 8), foreground="gray"
                ).grid(row=1, column=0, pady=(2, 0))

            return preview_frame
        # Create a placeholder with file type info
        placeholder = self._create_file_type_placeholder(preview_frame, file)
        if placeholder:
            placeholder.grid(row=0, column=0, sticky="n")
            return preview_frame

        return None

    def _create_preview_thumbnail(self, parent: ttk.Frame, file: FileMetadata) -> tk.Label | None:
        """
        Create a thumbnail preview for an image or video file.

        Args:
            parent: Parent widget to place the thumbnail
            file: File metadata to create preview for

        Returns:
            Label widget with thumbnail image, or None if preview not possible
        """
        try:
            # Check file size limit (max 50MB for preview generation)
            if file.size_mb > 50.0:
                return None

            # Check if file exists
            if not file.file_path.exists():
                return None

            extension = file.extension.lower()

            # Handle image files (expanded format support)
            image_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".tiff",
                ".tif",
                ".webp",
                ".ico",
                ".pcx",
                ".tga",
                ".dds",
            }

            # HEIC/HEIF files (require special handling)
            heic_extensions = {".heic", ".heif"}

            if extension in image_extensions:
                return self._create_image_thumbnail(parent, file)
            if extension in heic_extensions:
                return (
                    self._create_heic_thumbnail(parent, file)
                    if HEIF_SUPPORTED
                    else self._create_file_type_placeholder(parent, file, "HEIC Image")
                )

            # Handle video files
            if extension in {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}:
                return self._create_video_thumbnail(parent, file)

        except Exception as e:
            logger.warning(f"Could not create thumbnail for {file.filename}: {e}")

        return None

    def _create_image_thumbnail(self, parent: ttk.Frame, file: FileMetadata) -> tk.Label | None:
        """Create thumbnail for standard image files."""
        return self._create_thumbnail_from_pil(parent, file)

    def _create_heic_thumbnail(self, parent: ttk.Frame, file: FileMetadata) -> tk.Label | None:
        """Create thumbnail for HEIC/HEIF files."""
        if not HEIF_SUPPORTED:
            return None
        return self._create_thumbnail_from_pil(parent, file)

    def _create_thumbnail_from_pil(self, parent: ttk.Frame, file: FileMetadata) -> tk.Label | None:
        """Create thumbnail using PIL with enhanced error handling."""
        try:
            with Image.open(file.file_path) as img:
                # Store original dimensions for metadata
                original_size = img.size

                # Convert RGBA to RGB if necessary for better compatibility
                if img.mode in ("RGBA", "LA", "P"):
                    # Create white background for transparent images
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA" or img.mode == "LA":
                        background.paste(img, mask=img.split()[-1])
                    else:  # P mode
                        img = img.convert("RGBA")
                        background.paste(
                            img, mask=img.split()[-1] if len(img.split()) == 4 else None
                        )
                    img = background
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Calculate thumbnail size maintaining aspect ratio (larger preview)
                img.thumbnail((150, 150), Image.Resampling.LANCZOS)

                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(img)

                # Create label with better styling
                label = tk.Label(parent, image=photo, relief="solid", borderwidth=2, bg="white")
                label.image = photo  # Keep reference
                # Store original dimensions for metadata display
                label.original_size = original_size
                return label

        except Exception as e:
            logger.warning(f"Could not create thumbnail for {file.filename}: {e}")
            return None

    def _create_video_thumbnail(self, parent: ttk.Frame, file: FileMetadata) -> tk.Label | None:
        """Create enhanced thumbnail placeholder for video file."""
        return self._create_file_type_placeholder(parent, file, "VIDEO")

    def _create_file_type_placeholder(
        self, parent: ttk.Frame, file: FileMetadata, file_type: str = None
    ) -> tk.Label | None:
        """Create a placeholder with file type information."""
        try:
            # Determine file type if not provided
            if not file_type:
                extension = file.extension.lower()
                if extension in {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}:
                    file_type = "VIDEO"
                elif extension in {".mp3", ".wav", ".flac", ".aac", ".ogg"}:
                    file_type = "AUDIO"
                else:
                    file_type = extension.upper().lstrip(".") or "FILE"

            # Create enhanced placeholder with better design
            placeholder = Image.new("RGB", (150, 120), (240, 240, 240))

            try:
                from PIL import ImageDraw, ImageFont

                draw = ImageDraw.Draw(placeholder)

                # Draw file type icon based on type
                if file_type == "VIDEO":
                    # Video play icon
                    triangle_points = [(60, 40), (60, 80), (90, 60)]
                    draw.polygon(triangle_points, fill=(100, 100, 100))
                elif file_type.startswith("HEIC"):
                    # Camera icon (simple rectangle with circle)
                    draw.rectangle([50, 45, 100, 75], outline=(100, 100, 100), width=2)
                    draw.ellipse([65, 55, 85, 75], outline=(100, 100, 100), width=2)
                else:
                    # Generic file icon
                    draw.rectangle([60, 35, 90, 85], outline=(100, 100, 100), width=2)
                    draw.polygon([(90, 35), (90, 50), (105, 50)], fill=(100, 100, 100))

                # Add file type text with better positioning
                try:
                    # Try to use a better font
                    font = ImageFont.load_default()
                    text_bbox = draw.textbbox((0, 0), file_type, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_x = (150 - text_width) // 2
                    draw.text((text_x, 90), file_type, fill=(100, 100, 100), font=font)
                except (OSError, AttributeError):
                    # Fallback for text rendering
                    draw.text((55, 90), file_type[:8], fill=(100, 100, 100))

                # Add file size info
                size_text = f"{file.size_mb:.1f}MB"
                try:
                    size_bbox = draw.textbbox((0, 0), size_text, font=font)
                    size_width = size_bbox[2] - size_bbox[0]
                    size_x = (150 - size_width) // 2
                    draw.text((size_x, 105), size_text, fill=(120, 120, 120), font=font)
                except (OSError, AttributeError, UnboundLocalError):
                    draw.text((60, 105), size_text[:8], fill=(120, 120, 120))

            except ImportError:
                # Fallback if PIL ImageDraw is not available
                pass

            photo = ImageTk.PhotoImage(placeholder)
            label = tk.Label(parent, image=photo, relief="solid", borderwidth=2, bg="white")
            label.image = photo
            return label

        except Exception as e:
            logger.warning(f"Could not create placeholder for {file.filename}: {e}")
            return None

    def _delete_selected_files(self) -> None:
        """Delete the selected files with safety checks."""
        if not self.files_to_delete:
            return

        # Safety check: Ensure all files still exist
        existing_files = []
        missing_files = []
        for file_path in self.files_to_delete:
            if file_path.exists():
                existing_files.append(file_path)
            else:
                missing_files.append(file_path)

        if not existing_files:
            messagebox.showinfo("No Files to Delete", "No selected files exist anymore.")
            # Clear missing files from selection
            self.files_to_delete.clear()
            self._update_selection_summary()
            return

        # Show final confirmation with file details
        file_details = []
        total_size_mb = 0
        for file_path in existing_files:
            try:
                size_bytes = file_path.stat().st_size
                size_mb = size_bytes / (1024 * 1024)
                total_size_mb += size_mb
                file_details.append(f"• {file_path.name} ({size_mb:.1f} MB)")
            except OSError:
                file_details.append(f"• {file_path.name} (size unknown)")

        file_list = "\n".join(file_details)
        confirmation_msg = (
            f"⚠️  DELETE {len(existing_files)} FILES? ⚠️\n\n"
            f"This action cannot be undone!\n\n"
            f"Files to delete ({total_size_mb:.1f} MB total):\n\n{file_list}\n\n"
            f"Are you absolutely sure you want to permanently delete these files?"
        )

        # Show warning with missing files if any
        if missing_files:
            confirmation_msg += (
                f"\n\nNote: {len(missing_files)} files are already missing and will be skipped."
            )

        result = messagebox.askyesno(
            "⚠️ CONFIRM FILE DELETION ⚠️", confirmation_msg, icon="warning", default="no"
        )

        if not result:
            return

        # Perform deletion with error handling
        deleted_files = []
        failed_deletions = []

        try:
            import os
            import sys

            for file_path in existing_files:
                try:
                    if sys.platform == "darwin":  # macOS - move to trash if possible
                        try:
                            import subprocess

                            subprocess.run(
                                [
                                    "osascript",
                                    "-e",
                                    f'tell app "Finder" to delete POSIX file "{file_path}"',
                                ],
                                check=True,
                                capture_output=True,
                            )
                            deleted_files.append(file_path)
                            logger.info(f"Moved to trash: {file_path}")
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            # Fallback to permanent deletion
                            os.remove(file_path)
                            deleted_files.append(file_path)
                            logger.info(f"Permanently deleted: {file_path}")
                    else:
                        # For non-macOS systems, delete permanently
                        os.remove(file_path)
                        deleted_files.append(file_path)
                        logger.info(f"Deleted: {file_path}")

                except OSError as e:
                    failed_deletions.append((file_path, str(e)))
                    logger.error(f"Failed to delete {file_path}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error during deletion: {e}")
            messagebox.showerror("Deletion Error", f"An unexpected error occurred: {e}")
            return

        # Update the files_to_delete set to remove successfully deleted files
        for deleted_file in deleted_files:
            self.files_to_delete.discard(deleted_file)

        # Show results
        if deleted_files and not failed_deletions:
            messagebox.showinfo(
                "Deletion Complete",
                f"Successfully deleted {len(deleted_files)} file(s).\n\n"
                f"Space recovered: {total_size_mb:.1f} MB",
            )
        elif deleted_files and failed_deletions:
            failure_details = "\n".join(
                [f"• {path.name}: {error}" for path, error in failed_deletions]
            )
            messagebox.showwarning(
                "Partial Deletion",
                f"Successfully deleted: {len(deleted_files)} file(s)\n"
                f"Failed to delete: {len(failed_deletions)} file(s)\n\n"
                f"Failures:\n{failure_details}",
            )
        elif failed_deletions:
            failure_details = "\n".join(
                [f"• {path.name}: {error}" for path, error in failed_deletions]
            )
            messagebox.showerror(
                "Deletion Failed",
                f"Failed to delete {len(failed_deletions)} file(s):\n\n{failure_details}",
            )

        # Refresh the view to update the display
        self._update_selection_summary()
        if self.scan_result.duplicate_groups:
            self._load_current_group()

    def _get_image_dimensions(self, file: FileMetadata) -> str | None:
        """Get image dimensions as formatted string."""
        try:
            with Image.open(file.file_path) as img:
                width, height = img.size
                return f"{width} × {height}"
        except Exception:
            return None

    def _open_file_location(self, file: FileMetadata) -> None:
        """Open the file location in system file manager."""
        try:
            import subprocess
            import sys

            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", "-R", str(file.file_path)], check=False)
            elif sys.platform == "win32":  # Windows
                subprocess.run(["explorer", "/select,", str(file.file_path)], check=False)
            else:  # Linux and other Unix-like
                subprocess.run(["xdg-open", str(file.file_path.parent)], check=False)
        except Exception as e:
            logger.warning(f"Could not open file location for {file.filename}: {e}")
            messagebox.showwarning(
                "Cannot Open Location", f"Could not open file location:\n{file.file_path.parent}"
            )

    def _update_filtered_groups(self) -> None:
        """Update the list of filtered groups based on current filter status."""
        self.filtered_groups = GroupFilter.filter_by_resolution_status(
            self.scan_result.duplicate_groups,
            self.auto_results,
            self.filter_status
        )
        
        # Reset current group index if it's out of bounds
        if self.current_group_index >= len(self.filtered_groups):
            self.current_group_index = 0
    
    def _apply_filter(self) -> None:
        """Apply the selected filter and refresh the view."""
        self.filter_status = self.filter_var.get()
        self._update_filtered_groups()
        
        if self.filtered_groups:
            self.current_group_index = 0
            self._load_current_group()
        else:
            self.summary_label.config(text=f"No {self.filter_status} groups found")
    
    def _auto_select_current(self) -> None:
        """Auto-select files for deletion in the current group."""
        if not self.filtered_groups:
            return
            
        group = self.filtered_groups[self.current_group_index]
        result = self.auto_selector.analyze_group(group)
        
        if result is None:
            messagebox.showinfo(
                "Auto-Selection", 
                "Current group cannot be auto-selected:\n"
                "- Group must have exactly 2 files\n"
                "- Files must be visually similar\n"
                "- Clear suffix pattern preferred"
            )
            return
            
        if not self.auto_selector.can_auto_select(result):
            response = messagebox.askyesno(
                "Low Confidence Auto-Selection",
                f"Auto-selection confidence is low ({result.confidence:.1%}).\n\n"
                f"Reasoning: {result.reasoning}\n\n"
                "Apply selection anyway?",
                icon="warning"
            )
            if not response:
                return
        
        # Apply the auto-selection
        self.files_to_delete.update(result.files_to_delete)
        result.applied = True
        
        # Update auto_results
        existing_result = next(
            (r for r in self.auto_results if r.group.base_name == group.base_name), 
            None
        )
        if existing_result:
            existing_result.files_to_delete = result.files_to_delete
            existing_result.applied = result.applied
        else:
            self.auto_results.append(result)
        
        messagebox.showinfo(
            "Auto-Selection Applied",
            f"Auto-selected files for deletion in group '{group.base_name}'\n\n"
            f"Confidence: {result.confidence:.1%}\n"
            f"Reasoning: {result.reasoning}"
        )
        
        self._refresh_current_group()
    
    def _auto_select_all(self) -> None:
        """Auto-select files for deletion in all applicable groups."""
        if not self.scan_result.duplicate_groups:
            return
            
        # Show progress dialog
        progress_window = tk.Toplevel(self.window)
        progress_window.title("Auto-Selecting...")
        progress_window.geometry("400x150")
        progress_window.transient(self.window)
        progress_window.grab_set()
        
        progress_label = ttk.Label(progress_window, text="Analyzing groups for auto-selection...")
        progress_label.pack(pady=20)
        
        progress_bar = ttk.Progressbar(progress_window, mode="indeterminate")
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.start()
        
        progress_window.update()
        
        try:
            # Process all groups
            results = self.auto_selector.process_groups(
                self.scan_result.duplicate_groups,
                apply_selections=True
            )
            
            # Apply auto-selections to files_to_delete
            for result in results['auto_selected']:
                self.files_to_delete.update(result.files_to_delete)
            
            # Store results
            self.auto_results = results['auto_selected'] + results['low_confidence']
            
            # Generate summary
            summary = self.auto_selector.get_auto_selection_summary(results)
            
            progress_window.destroy()
            
            # Show results
            messagebox.showinfo(
                "Auto-Selection Complete",
                f"Auto-selection analysis complete!\n\n{summary}\n\n"
                "Use the filter controls to view resolved/unresolved groups."
            )
            
            # Update the filter to show unresolved groups by default
            self.filter_var.set("unresolved")
            self._apply_filter()
            
        except Exception as e:
            progress_window.destroy()
            logger.error(f"Error during auto-selection: {e}")
            messagebox.showerror(
                "Auto-Selection Error",
                f"An error occurred during auto-selection:\n{e}"
            )
        
        self._refresh_current_group()

    def show(self) -> None:
        """Show the review window."""
        self.window.focus_set()
        self.window.wait_window()
