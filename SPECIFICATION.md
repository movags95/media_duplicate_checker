# Duplicate Media Management Application

## 1. Filename-Based Duplicate Detection Strategy

### Core Detection Logic
The application will identify potential duplicates based on specific filename patterns:

#### Pattern Recognition Rules
1. Base Name Matching
   - Strip out numerical suffixes and extensions
   - Compare core filename components

#### Specific Matching Scenarios

##### Scenario 1: GUID-based Filenames
- Pattern: `[GUID].[extension]` and `[GUID]-[numbers].[extension]`
- Example: 
  - `58c9b580-5303-4b3b-b75d-f07f505f8d59.JPG`
  - `58c9b580-5303-4b3b-b75d-f07f505f8d59-222115.JPG`

##### Scenario 2: IMG Prefix Filenames
- Pattern: `IMG_[number].[extension]` and `IMG_[number]-[additional numbers].[extension]`
- Examples:
  - `IMG_1234.HEIC`
  - `IMG_1234-56788.HEIC`

##### Scenario 3: Complex Scenario Handling
- Ability to distinguish between:
  - Actual duplicates
  - Different images with similar naming


## 2. User Interface Requirements
### Main menu Interface
- Selecting a directory
- Scan the directory
- Review recent scan


### Duplicate Review Interface
- List view of potential duplicate groups
- Side-by-side file details:
  - Filename
  - File size
  - Creation date
  - Last modified date
- Preview pane for images/videos
- Checkboxes for selection/deletion

### User Actions
- Review each potential duplicate group
- Select which files to keep/delete
- View file details
- Quick preview of media files
- Batch decision support

## 3. Technical Specifications

### Technology Stack
- Language: Python
- Cross-platform desktop application
- Minimal external dependencies

### Performance Considerations
- Efficient file scanning for 40,000+ files
- Low memory footprint
- Background processing
- Quick preview generation

## 4. Filename Detection Challenges

### Handling Edge Cases
- Distinguish between:
  - Actual duplicates
  - Different files with similar names
- Flexible pattern matching
- User confirmation for ambiguous cases

### Pattern Recognition Limitations
- Relies on consistent naming conventions
- Manual review recommended
- Fallback to manual selection for complex scenarios

## 5. Proposed Implementation Approach

1. Filename Parsing Module
   - Develop robust filename parsing
   - Handle various naming patterns
   - Extract core identification components

2. Duplicate Grouping Engine
   - Group files by parsed base name
   - Identify potential duplicates
   - Prepare for user review

3. User Interface
   - Display grouped potential duplicates
   - Provide detailed file information
   - Enable user decision-making

## Development Considerations
- Prioritize accuracy over automated deletion
- Always require user confirmation
- Provide comprehensive file details
- Maintain original file integrity

## 6. Application considerations
- Easy to download from git and run
- Instructions for application available
