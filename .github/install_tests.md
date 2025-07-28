# Ad-Hoc Cross-Platform Install Tests

Quick guide for running cross-platform installation tests manually.

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
gh workflow run manual-cross-platform-test.yml -f test-from-pypi=true

# Test specific version
gh workflow run manual-cross-platform-test.yml \
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
gh workflow run manual-cross-platform-test.yml -f test-from-pypi=false
```

## Platforms Tested

- **Linux**: AMD64, ARM64
- **macOS**: Intel (AMD64), Apple Silicon (ARM64)
- **Windows**: AMD64
- **Python**: 3.10 and 3.13 on each platform

## What Gets Tested

1. **Package Installation**: `pip install langflow` or from built wheels
2. **CLI Help**: `langflow --help` 
3. **Server Startup**: `langflow run --backend-only` with HTTP health check
4. **Python Import**: `import langflow`

## Common Options

```bash
# Extended timeout (5 minutes instead of 2)
gh workflow run manual-cross-platform-test.yml \
  -f test-timeout=300

# Test specific PyPI version with longer timeout
gh workflow run manual-cross-platform-test.yml \
  -f test-from-pypi=true \
  -f langflow-version="1.0.17" \
  -f test-timeout=180
```

## Use Cases

- **Before releases**: Verify current branch works on all platforms
- **After PyPI publish**: Confirm published packages install correctly  
- **Debugging issues**: Test specific versions when users report problems
- **Development**: Quick cross-platform validation during feature work

## Results

- ✅ **Success**: All platforms pass installation and basic functionality
- ❌ **Failure**: One or more platforms fail (check logs for details)
- Each platform/Python combination runs independently