# Cross-Platform Install Tests

Guide for running cross-platform installation tests manually and programmatically.

## Available Tests

### 1. Test from PyPI
Tests published langflow packages from PyPI across all platforms.

**Via GitHub UI:**
1. Go to **Actions** → **Manual Cross-Platform Test**
2. Check **"Test from PyPI"**
3. Optionally specify a version (leave empty for latest)
4. Click **"Run workflow"**

**Via CLI:**
```bash
# Test latest version
gh workflow run cross-platform-test-manual.yml -f test-from-pypi=true

# Test specific version
gh workflow run cross-platform-test-manual.yml \
  -f test-from-pypi=true \
  -f langflow-version="1.0.18"
```

### 2. Test from Source
Builds and tests langflow from current branch source code.

**Via GitHub UI:**
1. Go to **Actions** → **Manual Cross-Platform Test**
2. Leave **"Test from PyPI"** unchecked
3. Click **"Run workflow"**

**Via CLI:**
```bash
# Test current branch
gh workflow run cross-platform-test-manual.yml -f test-from-pypi=false
```

## Platforms Tested

- **Linux**: AMD64
- **macOS**: Intel (AMD64), Apple Silicon (ARM64)
- **Windows**: AMD64
- **Python versions**:
  - **Linux & macOS**: 3.10 and 3.13
  - **Windows**: 3.10 and 3.12 (3.12 used instead of 3.13 for better stability)

## What Gets Tested

1. **Package Installation**: `uv pip install langflow` (PyPI) or local wheel installation
2. **Dependencies**: Additional packages like `openai` for full functionality
3. **CLI Help**: `langflow --help`
4. **Server Startup**: `langflow run --backend-only` with `/health_check` endpoint validation
5. **Python Import**: `import langflow`

## Common Options

```bash
# Extended timeout (10 minutes instead of default 5)
gh workflow run cross-platform-test-manual.yml \
  -f test-timeout=10

# Test specific PyPI version
gh workflow run cross-platform-test-manual.yml \
  -f test-from-pypi=true \
  -f langflow-version="1.0.18"
```

## Use Cases

- **Before releases**: Verify current branch works on all platforms
- **After PyPI publish**: Confirm published packages install correctly
- **Debugging issues**: Test specific versions when users report problems
- **Development**: Quick cross-platform validation during feature work

## Technical Details

### Installation Methods
- **PyPI testing**: Uses `uv pip install` with official PyPI packages
- **Source testing**: Builds wheels from source, then installs locally
- **Dependencies**: Automatically installs additional packages (`openai`) for full functionality

### Health Checking
- **Endpoint**: Uses `/health_check` for reliable server readiness validation
- **Validation**: Checks database connectivity and chat service functionality
- **Timeout**: Configurable timeout with proper cross-platform handling

### Platform-Specific Optimizations
- **Windows**: Uses Python 3.12 for better package ecosystem stability
- **Unix**: Uses Python 3.13 for latest language features where stable
- **Virtual Environments**: Uses `uv venv --seed` for consistent pip availability

### Workflow Architecture

```
Manual Entry Point:
└── cross-platform-test-manual.yml (workflow_dispatch)
    ├── PyPI Mode → cross-platform-test-shared.yml
    └── Source Mode → cross-platform-test.yml → cross-platform-test-shared.yml

Programmatic Entry Point:
└── cross-platform-test.yml (workflow_call only)
    └── cross-platform-test-shared.yml
```

- **Manual Workflow**: User-facing interface with PyPI/source options
- **Main Workflow**: Internal workflow for programmatic calls (CI, releases)
- **Shared Workflow**: Core test execution logic (matrix jobs)
- **Single Entry Point**: Use `cross-platform-test-manual.yml` for all manual testing

### Parameter Requirements

⚠️ **Important**: When calling reusable workflows from `workflow_dispatch` triggers, **all parameters must be explicitly provided**, even optional ones with defaults. Missing optional parameters can cause workflows to be silently skipped.

**Example of correct parameter passing:**
```yaml
uses: ./.github/workflows/cross-platform-test-shared.yml
with:
  install-method: "wheel" 
  test-timeout: 5
  langflow-version: ""          # ← Required even though optional
  base-artifact-name: "dist"
  main-artifact-name: "dist"  
  run-id: ""                   # ← Required even though optional
```

## Results

- ✅ **Success**: All platforms pass installation and basic functionality
- ❌ **Failure**: One or more platforms fail (check logs for details)
- Each platform/Python combination runs independently
- **Parallel execution**: All platforms tested simultaneously for faster feedback