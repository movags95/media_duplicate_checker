# Media Duplicate Checker

A cross-platform desktop application for detecting and managing duplicate media files based on filename patterns.

## Features

- **Filename-based duplicate detection** using pattern recognition
- **Support for multiple patterns**: GUID-based filenames, IMG_xxxx patterns, and generic numbered files
- **Cross-platform GUI** built with tkinter
- **Command-line interface** for automated workflows
- **Safe operation** - never auto-deletes files, always requires user confirmation
- **Performance optimized** for large directories (40,000+ files)
- **Comprehensive testing** with 56 test cases

## Supported Filename Patterns

### GUID Pattern
- `58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG`
- `58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG`

### IMG Pattern  
- `IMG_1234.HEIC`
- `IMG_1234-56788.HEIC`

### Generic Pattern
- Files with meaningful base names and potential suffixes

## Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd media_duplicate_checker
```

2. **Install UV (if not already installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Install dependencies:**
```bash
uv sync
```

## Usage

### GUI Mode (Default)

Launch the graphical interface:
```bash
uv run media-duplicate-checker
```

1. Click "Browse..." to select a directory
2. Click "Scan for Duplicates" to find potential duplicates
3. Click "Review Last Scan" to examine and manage duplicates
4. Use the review interface to select files for deletion

### Command Line Mode

Scan a directory from the command line:
```bash
# Basic scan
uv run media-duplicate-checker --scan /path/to/photos

# Detailed output with file information  
uv run media-duplicate-checker --scan /path/to/photos --detailed

# Non-recursive scan (current directory only)
uv run media-duplicate-checker --scan . --no-recursive

# JSON output for scripting
uv run media-duplicate-checker --scan /path/to/photos --output-format json

# Enable debug logging
uv run media-duplicate-checker --scan /path/to/photos --log-level DEBUG
```

### Available Commands

```bash
uv run media-duplicate-checker --help    # Show help
uv run media-duplicate-checker --version # Show version
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest src/media_duplicate_checker/core/tests/test_parser.py -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .

# Type checking
uv run mypy src/
```

### Project Structure

```
src/media_duplicate_checker/
├── cli/                    # Command-line interface
├── core/                   # Core business logic
│   ├── models.py          # Pydantic data models
│   ├── parser.py          # Filename parsing logic
│   ├── scanner.py         # File system scanning
│   ├── grouper.py         # Duplicate grouping logic
│   └── tests/             # Unit tests
├── ui/                    # GUI components
│   ├── main_window.py     # Main application window
│   └── review_window.py   # Duplicate review interface
└── main.py               # Application entry point
```

## Configuration

The application uses sensible defaults but can be customized:

- **Supported file extensions**: jpg, jpeg, png, gif, bmp, tiff, webp, mp4, mov, avi, mkv, wmv, flv, webm, heic, heif
- **Preview size limit**: 50MB
- **Line length**: 100 characters
- **Python version**: 3.12+

## Safety Features

- **No automatic deletion**: All file operations require explicit user confirmation
- **Preview before action**: Review interface shows detailed file information
- **Confidence scoring**: Files are ranked by likelihood of being duplicates
- **Pattern validation**: Robust filename pattern matching with fallbacks

## Supported Media Types

- **Images**: JPG, JPEG, PNG, GIF, BMP, TIFF, WebP, HEIC, HEIF
- **Videos**: MP4, MOV, AVI, MKV, WMV, FLV, WebM

## Requirements

- Python 3.12+
- tkinter (usually included with Python)
- UV package manager
- Cross-platform: Windows, macOS, Linux

## License

This project follows the CLAUDE.md development guidelines and emphasizes safety, simplicity, and user control.