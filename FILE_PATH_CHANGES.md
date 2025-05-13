# Preserve Original Filenames in File Processing

## Description
Currently, when using the File component or any component based on BaseFileComponent, the `file_path` of the returned Data objects is set to a location within the Langflow file cache with a random UUID as the filename. This makes it difficult to track and identify files in the system. This PR adds support for preserving original filenames and archive metadata to improve file traceability and user experience.

## Changes
- Added `get_original_filename` helper method to `BaseFileComponent` in `src/backend/base/langflow/base/data/base_file.py` to:
  - Retrieve original filenames from the database
  - Handle cross-platform cache directory paths using `platformdirs`
  - Provide fallback to UUID-based filenames if database lookup fails

- Modified `parse_text_file_to_data` in `src/backend/base/langflow/base/data/utils.py` to:
  - Extract and store original filenames
  - Keep cached paths for backward compatibility
  - Add original filename to metadata

- Updated `_unpack_and_collect_files` in `src/backend/base/langflow/base/data/base_file.py` to:
  - Store original archive names and paths
  - Preserve original filenames for extracted files
  - Add archive metadata to Data objects
  - Skip platform-specific hidden files (e.g., macOS `._` files)
  - Maintain proper error handling and cleanup

## Testing
Added new tests to verify the changes:

1. Backend Tests:
   - `test_directory_preserves_original_filenames`: Verifies original filename preservation
   - `test_directory_handles_archives_with_original_filenames`: Tests archive handling with metadata
   - `test_cross_platform_cache_paths`: Verifies cache directory handling across platforms
   - `test_database_filename_lookup`: Tests database integration for filename retrieval

2. Frontend Tests:
   - `should display original filenames correctly`: Verifies UI display of original filenames
   - `should handle archive metadata properly`: Tests archive metadata display

## Benefits
- Improved file traceability through preserved original filenames
- Better context for archived files with archive metadata
- Enhanced user experience with meaningful filenames
- Maintained backward compatibility with existing code
- Cross-platform compatibility for cache directories
- Robust error handling with fallback mechanisms

## Components Affected
- BaseFileComponent
- File component
- Any components inheriting from BaseFileComponent
- Database service for filename lookups

## Implementation Details
1. Database Integration:
   - Original filenames are stored in the database when files are uploaded
   - Files are looked up by their relative path within the cache directory
   - Fallback to UUID-based filenames if database lookup fails

2. Cross-Platform Support:
   - Cache directory paths are determined using `platformdirs`
   - Works on Linux, macOS, and Windows
   - Handles platform-specific file attributes (e.g., macOS hidden files)

3. Archive Handling:
   - Original archive names are preserved
   - Files extracted from archives maintain their original names
   - Archive metadata is included in the Data objects

## Future Considerations
1. Add configuration options for filename handling
2. Implement filename sanitization
3. Add migration tools for existing cached files
4. Enhance error handling and logging
5. Add performance optimizations for database lookups

## Related Issues
Closes #[issue_number] 