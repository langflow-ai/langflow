# Investigation: PyTorch on macOS AMD64 (x86_64) + Python 3.13

**Jira:** LE-172  
**Date:** 2026-04-02  
**Status:** Complete  

---

## TL;DR

**PyTorch officially dropped macOS x86_64 (Intel) binary support after version 2.2.2** (milestone: PyTorch 2.3, March 2024). Since Python 3.13 was released in October 2024 — after this cutoff — **no official PyTorch wheel exists for macOS x86_64 + Python 3.13**. This is an upstream, permanent gap — not a bug in Langflow.

The failing CI job is `test-installation-experimental` on `macos-latest-large` (AMD64) with Python 3.13. The `continue-on-error: true` flag means it doesn't block releases, but the failure is persistent and expected.

---

## Root Cause Analysis

### 1. PyTorch macOS x86_64 Deprecation Timeline

| Event | Date | Reference |
|-------|------|-----------|
| RFC opened to deprecate macOS x86_64 builds | Nov 2023 | [pytorch/pytorch#114602](https://github.com/pytorch/pytorch/issues/114602) |
| PyTorch 2.2.2 released (last x86_64 macOS wheels) | March 2024 | Last version with `cp310`, `cp311`, `cp312` macOS x86_64 wheels |
| PyTorch 2.3.0 released (no macOS x86_64 wheels) | April 2024 | Milestone for x86_64 deprecation |
| Python 3.13 released | Oct 2024 | After PyTorch dropped macOS x86_64 |

**Key fact:** PyTorch 2.2.2 has macOS x86_64 wheels for Python 3.10, 3.11, 3.12 — but **not 3.13**. And PyTorch 2.3+ does not publish macOS x86_64 wheels at all.

### 2. What the UV Resolver Does

When resolving for `macOS x86_64 + Python 3.13`, the uv lockfile shows:

```
torch 2.2.2        → Python < 3.13, macOS x86_64  (has wheels: cp310, cp311, cp312)
torch 2.2.2+cpu    → Python >= 3.13, macOS x86_64  (NO WHEELS listed!)
torch 2.10.0       → macOS arm64 (all Python versions)
torch 2.10.0+cpu   → Linux/Windows (all Python versions)
```

The resolver picks `torch 2.2.2+cpu` for macOS x86_64 + Python 3.13, but **this version has zero available wheels** for that platform. Installation fails because there's no compatible binary.

### 3. How Torch Gets Pulled In

The main `langflow` package depends on `langflow-base[complete]`, which includes multiple extras that transitively require torch:

#### Dependency Chains to Torch

| Extra | Chain | macOS x86_64 Excluded? |
|-------|-------|----------------------|
| `altk` | `agent-lifecycle-toolkit` → torch (direct dep) | **No** |
| `altk` | `agent-lifecycle-toolkit` → `sentence-transformers` → torch | **No** |
| `altk` | `agent-lifecycle-toolkit` → `trl` → `accelerate` → torch | **No** |
| `docling` | `docling` → `docling-ibm-models` → torch | Partially (docling binary excluded, but `docling-core` is not) |
| `easyocr` | `easyocr` → torch | **Yes** (fully excluded on macOS x86_64) |
| `langchain-huggingface` | `langchain-huggingface` → `sentence-transformers` → torch | **No** |

**The ALTK extra is the primary unguarded path** that forces torch installation on macOS x86_64. The issue was initially noticed with ALTK but the root cause is PyTorch's platform support.

### 4. Existing Mitigations

The codebase already excludes some torch-dependent packages on macOS x86_64:

```toml
# src/backend/base/pyproject.toml
docling = [
    "docling-core>=2.36.1,<3.0.0",
    "docling>=2.36.1,<3.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'",
]
easyocr = ["easyocr>=1.7.2,<2.0.0; sys_platform != 'darwin' or platform_machine != 'x86_64'"]
```

However, **ALTK** and **langchain-huggingface** (which depends on sentence-transformers → torch) have **no such platform exclusion**.

### 5. CI Configuration

The experimental job in `.github/workflows/cross-platform-test.yml`:
- Tests Python 3.13 on all platforms including macOS AMD64
- Uses `continue-on-error: true` so failures don't block releases
- The test-summary job considers experimental failures "acceptable"

---

## Recommendations

### Option A: Exclude torch-dependent extras on macOS x86_64 (Recommended)

Add platform markers to all extras that transitively depend on torch, similar to what's done for `easyocr`:

```toml
# In src/backend/base/pyproject.toml
altk = ["agent-lifecycle-toolkit~=0.4.4; sys_platform != 'darwin' or platform_machine != 'x86_64'"]
langchain-huggingface = ["langchain-huggingface==0.3.1; sys_platform != 'darwin' or platform_machine != 'x86_64'"]
```

**Pros:**
- CI will pass on all experimental platforms
- macOS x86_64 users on Python 3.13 can still use Langflow (just without ALTK/HuggingFace features)
- Consistent with existing pattern for docling/easyocr

**Cons:**
- Reduces feature availability on macOS x86_64
- All Python versions on macOS x86_64 lose these features (not just 3.13)

### Option B: Add Python version + platform compound markers

More surgical approach — only exclude on the exact broken combination:

```toml
altk = ["agent-lifecycle-toolkit~=0.4.4; (sys_platform != 'darwin' or platform_machine != 'x86_64' or python_version < '3.13')"]
```

**Pros:**
- Preserves functionality on macOS x86_64 + Python 3.10-3.12
- Only excludes the broken combination

**Cons:**
- More complex markers
- PEP 508 marker evaluation of compound OR conditions can be tricky across tools

### Option C: Remove macOS AMD64 from experimental CI matrix (Simplest)

Since macOS x86_64 is a dying platform (Apple stopped selling Intel Macs in 2022), remove it from CI:

```yaml
# Remove this entry from the experimental matrix:
# - os: macos
#   arch: amd64
#   runner: macos-latest-large
#   python-version: "3.13"
```

**Pros:**
- Simplest fix (one line change)
- Saves CI runner costs (macos-latest-large is expensive)
- Reflects reality that macOS Intel is EOL

**Cons:**
- Loses visibility into macOS x86_64 regressions
- Some users may still be on Intel Macs

### Option D: Keep as-is (Status Quo)

The experimental job already uses `continue-on-error: true` and the test-summary job reports it as acceptable. This failure is a known, documented limitation.

**Pros:**
- No code changes needed
- Maintains CI visibility

**Cons:**
- Persistent red CI job creates alert fatigue
- Could mask other real failures in the experimental matrix

---

## Recommendation

**Option A + Option C combined** is the strongest approach:

1. **Add platform exclusion markers** to `altk` and `langchain-huggingface` extras for macOS x86_64 (Option A). This prevents installation failures for end users on Intel Macs.

2. **Optionally remove macOS AMD64 from the Python 3.13 experimental matrix** (Option C) to reduce CI costs and noise, since the platform is EOL from both Apple and PyTorch.

The combination ensures both end-user experience and CI health. The feature loss on macOS Intel is acceptable because:
- Apple stopped producing Intel Macs in June 2022
- PyTorch dropped Intel Mac support in March 2024
- The HuggingFace/ML ecosystem is rapidly moving to ARM-only on macOS

---

## Appendix: Affected Lockfile Entries

### torch versions resolved by platform

| Version | Platform | Python | Has Wheels? |
|---------|----------|--------|-------------|
| `2.2.2` | macOS x86_64 | < 3.13 | Yes (cp310, cp311, cp312) |
| `2.2.2+cpu` | macOS x86_64 | >= 3.13 | **No** |
| `2.10.0` | macOS arm64 | all | Yes (cp310-cp313) |
| `2.10.0+cpu` | Linux/Windows | all | Yes (cp310-cp313) |

### torchvision versions resolved by platform

| Version | Platform | Python | Has Wheels? |
|---------|----------|--------|-------------|
| `0.17.2` | macOS x86_64 | < 3.13 | Yes (cp310, cp311, cp312) |
| `0.17.2+cpu` | macOS x86_64 | >= 3.13 | **No** |
| `0.25.0` | macOS arm64 | all | Yes |
| `0.25.0+cpu` | Linux/Windows | all | Yes |
