# Dynamic Coverage Configuration

This script generates a custom `.coveragerc` file for backend testing that excludes:

1. **Bundled components** - Components listed in `SIDEBAR_BUNDLES` from `src/frontend/src/utils/styleUtils.ts`
2. **Legacy components** - Python files containing `legacy = True`

## How it works

1. **Reads frontend config**: Parses `styleUtils.ts` to extract bundled component names
2. **Scans backend files**: Finds all `.py` files in `src/backend/base/langflow/components/` with `legacy = True`
3. **Generates .coveragerc**: Creates exclusion patterns for pytest-cov

## Usage

### Local development
```bash
# Generate config and run tests
python3 scripts/generate_coverage_config.py
cd src/backend && python -m pytest --cov=src/backend/base/langflow --cov-config=.coveragerc
```

### CI Integration
The script runs automatically in CI before backend tests via `.github/workflows/python_test.yml`.

## Files affected

- **Input**: `src/frontend/src/utils/styleUtils.ts` (SIDEBAR_BUNDLES)
- **Input**: `src/backend/base/langflow/components/**/*.py` (legacy components)
- **Output**: `src/backend/.coveragerc` (auto-generated, in .gitignore)

## Benefits

- **Accurate coverage**: Focuses on actively maintained core code
- **Dynamic updates**: Automatically adapts when bundles/legacy components change
- **Codecov compatible**: Generated config works with both local testing and Codecov reporting