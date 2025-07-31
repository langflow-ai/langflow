# Cross-Platform Install Tests

Unified workflow for testing langflow installation across multiple platforms, supporting both manual and programmatic execution.

## Manual Testing

### 1. Test from PyPI
Tests published langflow packages from PyPI across all platforms.

**Via GitHub UI:**
1. Go to **Actions** → **Cross-Platform Installation Test**
2. Check **"Test from PyPI instead of building from source"**
3. Optionally specify a version (leave empty for latest)
4. Click **"Run workflow"**

**Via CLI:**
```bash
# Test latest version
gh workflow run cross-platform-test.yml -f test-from-pypi=true

# Test specific version
gh workflow run cross-platform-test.yml \
  -f test-from-pypi=true \
  -f langflow-version="1.0.18"
```

### 2. Test from Source
Builds and tests langflow from current branch source code.

**Via GitHub UI:**
1. Go to **Actions** → **Cross-Platform Installation Test**
2. Leave **"Test from PyPI instead of building from source"** unchecked
3. Click **"Run workflow"**

**Via CLI:**
```bash
# Test current branch
gh workflow run cross-platform-test.yml -f test-from-pypi=false
```

## Programmatic Testing

For CI, releases, and other automated workflows that test wheel installation:

```yaml
jobs:
  test-cross-platform:
    uses: ./.github/workflows/cross-platform-test.yml
    with:
      base-artifact-name: "dist-base"
      main-artifact-name: "dist-main"
      test-timeout: 120  # optional, defaults to 5
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
gh workflow run cross-platform-test.yml \
  -f test-timeout=10

# Test specific PyPI version
gh workflow run cross-platform-test.yml \
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

**Unified Single-File Design:**

```
cross-platform-test.yml
├── workflow_dispatch (Manual UI)
│   ├── PyPI Testing (test-from-pypi=true)
│   └── Source Testing (test-from-pypi=false)
└── workflow_call (Programmatic API)
    └── Wheel Testing (always uses wheel method)
```

**Key Benefits:**
- **Single File**: No complex workflow chains or parameter passing issues
- **Unified Logic**: Same test matrix for all use cases  
- **Smart Routing**: Automatically determines install method based on trigger type
- **Context-Aware**: Summary messages adapt to manual vs programmatic usage

### Trigger Types

**Manual (`workflow_dispatch`):**
- Simple boolean toggle: "Test from PyPI" vs "Test from Source"
- User-friendly parameter names
- Context-specific success/failure messages

**Programmatic (`workflow_call`):**
- Full parameter control for CI/releases
- Backward compatible with existing workflows
- Always uses wheel installation method (tests built artifacts)

### Implementation Details

The workflow uses dynamic job conditions to route execution:

```yaml
# Build only runs for source testing or when no artifacts provided
build-if-needed:
  if: |
    (github.event_name == 'workflow_dispatch' && inputs.test-from-pypi == false) ||
    (github.event_name == 'workflow_call' && (inputs.base-artifact-name == '' || inputs.main-artifact-name == ''))

# Test matrix adapts install method based on trigger
test-installation:
  steps:
    - name: Determine install method
      # workflow_dispatch: maps boolean to install method  
      # workflow_call: always uses wheel method
    - name: Install from PyPI
      if: steps.install-method.outputs.method == 'pypi'
    - name: Install from wheels  
      if: steps.install-method.outputs.method == 'wheel'
```

## Results

- ✅ **Success**: All platforms pass installation and basic functionality
- ❌ **Failure**: One or more platforms fail (check logs for details)
- Each platform/Python combination runs independently
- **Parallel execution**: All platforms tested simultaneously for faster feedback