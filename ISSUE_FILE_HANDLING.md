# Enhance File Handling to Preserve Original Filenames

## Problem
Currently, when files are processed in Langflow (through File component or BaseFileComponent), the original filenames are lost as they are stored in the cache with random UUIDs. For example:
```
/Users/jeffreycarpenter/Library/Caches/langflow/9b25ba34-bd1f-40f6-a732-1278d07c751f/d62d6307-0509-407a-9abc-bae57eb02882.pdf
```

This creates several issues:
1. Difficult to track which file is which in the system
2. Loss of context when working with multiple files
3. Poor user experience when files are displayed with random names
4. No way to maintain relationships between files extracted from archives

## Implemented Solution
Added support for preserving original filenames and archive metadata by:
1. Storing original filenames in the database and retrieving them during processing
2. Maintaining archive context for extracted files
3. Keeping the cached paths for backward compatibility
4. Using platform-specific cache directories for cross-platform compatibility

### Technical Details
- Added `get_original_filename` helper method to `BaseFileComponent` to retrieve original filenames from the database
- Added `original_filename` field to Data objects
- Added `archive_name` and `archive_path` fields for files from archives
- Updated file processing components to handle the new metadata
- Ensured backward compatibility with existing code
- Used `platformdirs` library for cross-platform cache directory handling

## Benefits
- Improved file traceability
- Better context for archived files
- Enhanced user experience
- Maintained backward compatibility
- Cross-platform compatibility

## Implementation Details
1. Database Integration:
   - Original filenames are stored in the database when files are uploaded
   - Files are looked up by their relative path within the cache directory
   - Fallback to UUID-based filenames if database lookup fails

2. Archive Handling:
   - Original archive names are preserved
   - Files extracted from archives maintain their original names
   - Archive metadata is included in the Data objects

3. Cross-Platform Support:
   - Cache directory paths are determined using `platformdirs`
   - Works on Linux, macOS, and Windows
   - Handles platform-specific file attributes (e.g., macOS hidden files)

## Questions for Discussion
1. Should we add a configuration option to control this behavior?
2. Do we need a migration path for existing cached files?
3. Should we add filename sanitization to handle special characters?
4. Are there any performance concerns with storing additional metadata?

## Implementation Plan
1. Modify `parse_text_file_to_data` to include original filenames
2. Update `_unpack_and_collect_files` to handle archive metadata
3. Add tests for the new functionality
4. Update documentation

## Related Components
- BaseFileComponent
- File component
- Any components inheriting from BaseFileComponent
- Database service for filename lookups

## Additional Context
This enhancement would be particularly useful for:
- Users working with multiple files
- Processing archived content
- Debugging and troubleshooting
- File organization and management

## Future Considerations
1. Add configuration options for filename handling
2. Implement filename sanitization
3. Add migration tools for existing cached files
4. Enhance error handling and logging
5. Add performance optimizations for database lookups 