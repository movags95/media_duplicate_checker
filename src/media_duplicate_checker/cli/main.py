"""CLI entry point for media duplicate checker."""

import argparse
import logging
import sys
from pathlib import Path

from ..core import ApplicationConfig, DuplicateGrouper, MediaFileScanner, ScanResult
from ..ui import MainWindow


def setup_logging(level: str = "INFO") -> None:
    """
    Set up logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def scan_directory_cli(
    directory: Path, recursive: bool = True, output_format: str = "text"
) -> ScanResult:
    """
    Scan a directory for duplicates from the command line.

    Args:
        directory: Directory to scan
        recursive: Whether to scan recursively
        output_format: Output format (text, json)

    Returns:
        ScanResult object with scan results
    """
    logger = logging.getLogger(__name__)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    # Initialize components
    config = ApplicationConfig()
    scanner = MediaFileScanner(config)
    grouper = DuplicateGrouper()

    # Progress callback for CLI
    def progress_callback(current: int, total: int | None = None, message: str = "") -> None:
        if message:
            print(f"\r{message}", end="", flush=True)
        elif total:
            percent = (current / total) * 100
            print(f"\rProgress: {current}/{total} ({percent:.1f}%)", end="", flush=True)
        else:
            print(f"\rProcessed: {current} files", end="", flush=True)

    try:
        logger.info(f"Starting scan of directory: {directory}")

        # Scan for media files
        print(f"Scanning directory: {directory}")
        media_files = scanner.scan_directory(
            directory, recursive=recursive, progress_callback=progress_callback
        )
        print()  # New line after progress

        # Group duplicates
        print("Analyzing for duplicates...")
        duplicate_groups = grouper.create_duplicate_groups(media_files)

        # Create scan result

        scan_result = ScanResult(
            scan_path=directory,
            total_files_found=len(media_files),  # Simplified for CLI
            media_files_found=len(media_files),
            duplicate_groups=duplicate_groups,
            scan_duration_seconds=1.0,  # Would need proper timing
        )

        logger.info(f"Scan complete: {len(duplicate_groups)} duplicate groups found")
        return scan_result

    except Exception as e:
        logger.error(f"Error during scan: {e}")
        raise


def print_scan_results(scan_result: ScanResult, detailed: bool = False) -> None:
    """
    Print scan results to console.

    Args:
        scan_result: Results from the scan operation
        detailed: Whether to show detailed file information
    """
    print("\n" + "=" * 60)
    print("SCAN RESULTS")
    print("=" * 60)

    print(f"Directory scanned: {scan_result.scan_path}")
    print(f"Media files found: {scan_result.media_files_found}")
    print(f"Duplicate groups: {len(scan_result.duplicate_groups)}")
    print(f"Potential duplicates: {scan_result.potential_duplicates_count}")
    print(f"Potential space savings: {scan_result.potential_space_savings_mb:.1f} MB")

    if not scan_result.duplicate_groups:
        print("\n✅ No duplicates found!")
        return

    print("\n" + "-" * 60)
    print("DUPLICATE GROUPS")
    print("-" * 60)

    for i, group in enumerate(scan_result.duplicate_groups, 1):
        print(f"\nGroup {i}: '{group.base_name}' ({group.pattern_type})")
        print(f"  Files: {group.file_count}")
        print(f"  Total size: {group.total_size_mb:.1f} MB")
        print(f"  Confidence: {group.confidence_score:.0%}")

        if detailed:
            print("  Files:")
            for file in group.files:
                print(f"    - {file.filename} ({file.size_mb:.1f} MB)")
                print(f"      Path: {file.file_path}")
                print(f"      Created: {file.created_at.strftime('%Y-%m-%d %H:%M')}")

            # Show recommendations
            largest = group.get_largest_file()
            newest = group.get_newest_file()

            if largest:
                print(f"  💡 Largest file: {largest.filename}")
            if newest:
                print(f"  💡 Newest file: {newest.filename}")


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Media Duplicate Checker - Find duplicate media files based on filename patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch GUI
  media-duplicate-checker

  # Scan directory from command line
  media-duplicate-checker --scan /path/to/photos

  # Scan with detailed output
  media-duplicate-checker --scan /path/to/photos --detailed

  # Scan only current directory (non-recursive)
  media-duplicate-checker --scan . --no-recursive

  # Enable debug logging
  media-duplicate-checker --scan /path/to/photos --log-level DEBUG
        """,
    )

    # Main action
    parser.add_argument(
        "--scan",
        type=Path,
        metavar="DIRECTORY",
        help="Scan directory for duplicates (command-line mode)",
    )

    # Scan options
    parser.add_argument(
        "--no-recursive", action="store_true", help="Don't scan subdirectories recursively"
    )

    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed file information in results"
    )

    # Output options
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format for results (default: text)",
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    return parser


def main() -> int:
    """
    Main entry point for the CLI application.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        if args.scan:
            # Command-line mode
            logger.info("Running in CLI mode")

            recursive = not args.no_recursive
            scan_result = scan_directory_cli(
                directory=args.scan, recursive=recursive, output_format=args.output_format
            )

            if args.output_format == "json":
                import json

                # Convert to JSON (would need proper serialization)
                print(
                    json.dumps(
                        {
                            "scan_path": str(scan_result.scan_path),
                            "media_files_found": scan_result.media_files_found,
                            "duplicate_groups_count": len(scan_result.duplicate_groups),
                            "potential_duplicates": scan_result.potential_duplicates_count,
                            "potential_savings_mb": scan_result.potential_space_savings_mb,
                        },
                        indent=2,
                    )
                )
            else:
                print_scan_results(scan_result, detailed=args.detailed)

        else:
            # GUI mode
            logger.info("Running in GUI mode")

            try:
                import tkinter as tk
            except ImportError:
                print("Error: tkinter is not available. GUI mode requires tkinter.")
                print("Try running with --scan option for command-line mode.")
                return 1

            app = MainWindow()
            app.run()

        return 0

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except NotADirectoryError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
