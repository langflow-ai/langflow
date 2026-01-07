# Starter Projects JSON Validation Tests

## Overview
This directory contains comprehensive unit tests for validating the structure and configuration of Langflow starter project JSON files.

## Test Files

### test_starter_projects_json_validation.py
Comprehensive validation tests for starter project JSON files, focusing on:
- JSON structure and syntax validation
- Note node backgroundColor configuration
- Node structure integrity
- File formatting and encoding
- Backward compatibility

## Running Tests

### Run all tests in this directory
```bash
pytest src/backend/tests/unit/initial_setup/starter_projects/ -v
```

### Run specific test file
```bash
pytest src/backend/tests/unit/initial_setup/starter_projects/test_starter_projects_json_validation.py -v
```

### Run with coverage
```bash
pytest src/backend/tests/unit/initial_setup/starter_projects/test_starter_projects_json_validation.py --cov --cov-report=html
```

### Run specific test class
```bash
pytest src/backend/tests/unit/initial_setup/starter_projects/test_starter_projects_json_validation.py::TestNoteNodeBackgroundColors -v
```

## Test Coverage

The test suite validates:

1. **JSON Structure** - Files exist, valid JSON, proper structure
2. **Note Node Colors** - backgroundColor values are correct (neutral/transparent, not emerald)
3. **Node Integrity** - All nodes have required fields and unique IDs
4. **File Format** - UTF-8 encoding, reasonable file sizes
5. **Backward Compatibility** - Documents intentional changes
6. **Edge Cases** - Handles malformed data, unexpected values

## Adding New Tests

When adding new starter projects or modifying existing ones:

1. Add the filename to `STARTER_PROJECT_FILES` constant
2. Update `VALID_NOTE_BACKGROUND_COLORS` if introducing new colors
3. Add project-specific validation in `TestSpecificProjectValidation` class
4. Run tests to ensure validation passes

## Test Philosophy

These tests follow pytest best practices:
- Parametrized tests for consistency across files
- Clear, descriptive test names
- Comprehensive docstrings
- Fast execution
- No external dependencies

## Maintenance

When modifying starter project JSON files:
1. Run these tests before committing changes
2. Update tests if schema changes
3. Document intentional breaking changes
4. Keep test coverage above 90%