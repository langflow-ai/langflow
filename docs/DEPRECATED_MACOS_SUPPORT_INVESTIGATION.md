# Investigation: Deprecated macOS Support — Impact on Langflow

**Jira:** LE-265  
**Date:** 2026-04-02  
**Status:** Complete  
**Related:** LE-172 (PyTorch macOS x86_64 + Python 3.13 — resolved in PR #12469)

---

## TL;DR

macOS Intel (x86_64) is in its final phase of deprecation across the entire ecosystem — Apple hardware, operating system, GitHub Actions runners, PyTorch, and the broader ML/AI stack. Langflow already has platform exclusion markers for the most critical torch-dependent extras (PR #12469), but additional deprecations in GitHub Actions runners, macOS versions, and upstream dependencies will require further action over the next 12–18 months.

**Key decision required:** Set a timeline to officially drop macOS x86_64 from Langflow's support matrix (recommended: Langflow 2.0 or Q4 2026, whichever comes first).

---

## 1. Deprecation Landscape

### 1.1 Apple Hardware & OS Timeline

| Event | Date | Impact |
|-------|------|--------|
| Last Intel MacBook Pro shipped | June 2022 | No new Intel Mac hardware |
| macOS Ventura 13 (last Intel-supported release rumoured) | Oct 2022 | Still receiving security updates as of early 2026 |
| macOS Sequoia 15 released | Sept 2024 | Supports some Intel Macs — expected to be last |
| macOS 26 (Tahoe) expected | June 2026 | Likely final macOS version supporting any Intel Mac |
| macOS 27 expected | 2027 | **Expected to drop all Intel Mac support** |

**Key fact:** Apple's Rosetta 2 translates x86_64 binaries on Apple Silicon, but native ARM64 builds are preferred. Rosetta support for macOS is expected to continue but individual frameworks (e.g., Metal 3) are ARM-only.

### 1.2 GitHub Actions Runner Deprecation

| Runner | Architecture | Status | Deprecation |
|--------|-------------|--------|-------------|
| `macos-13` | Intel x86_64 | **Deprecated** | Removed Dec 2025 |
| `macos-14` | ARM64 (M1) | Active | Current |
| `macos-15` | ARM64 (M1/M2) | Active | Current |
| `macos-latest` | ARM64 | Active | Points to macos-15 |
| `macos-latest-large` | Intel x86_64 | **Active but costly** | At risk — GitHub shifting to ARM |
| `macos-26` (Tahoe) | ARM64 | Available | Current |

**Key fact:** `macos-latest-large` is the **only** Intel x86_64 runner available. It is one of the most expensive GitHub Actions runners. GitHub has signaled the shift toward ARM-only macOS runners.

### 1.3 PyTorch macOS x86_64 Deprecation

| Event | Date |
|-------|------|
| RFC to deprecate macOS x86_64 builds | Nov 2023 |
| PyTorch 2.2.2 — last Intel Mac wheels (`cp310`, `cp311`, `cp312`) | March 2024 |
| PyTorch 2.3.0 — no Intel Mac wheels at all | April 2024 |
| Python 3.13 released (no PyTorch wheels for Intel Mac) | Oct 2024 |

**Result:** No PyTorch wheel exists for macOS x86_64 + Python ≥ 3.13. PyTorch 2.2.2 is the last version with Intel Mac support, and it only covers Python 3.10–3.12.

### 1.4 Broader ML Ecosystem

| Library | macOS x86_64 Support | Notes |
|---------|---------------------|-------|
| PyTorch | ❌ Dropped (after 2.2.2) | No wheels for Python 3.13+ on Intel |
| MLX | ❌ Never supported | Apple Silicon only (arm64 + Python 3.12+) |
| MLX-VLM | ❌ Never supported | Apple Silicon only |
| Metal SDK | ❌ ARM64 only | Metal 3 requires Apple Silicon |
| TensorFlow | ⚠️ Limited | `tensorflow-macos` deprecated, replaced by `tensorflow-metal` (ARM64) |
| ONNX Runtime | ✅ Still supported | Cross-platform, but CoreML EP is ARM64-optimized |
| sentence-transformers | ⚠️ Transitively broken | Depends on PyTorch — fails on Intel Mac + Python 3.13 |
| Hugging Face Transformers | ⚠️ Transitively broken | Same PyTorch dependency chain |

---

## 2. Current State of Langflow macOS Support

### 2.1 Platform Exclusion Markers in `pyproject.toml`

The following extras have platform markers excluding macOS x86_64 (**as of PR #12469**):

| Extra | Marker | Reason |
|-------|--------|--------|
| `altk` | `sys_platform != 'darwin' or platform_machine != 'x86_64'` | PyTorch direct + transitive dep (PR #12469) |
| `langchain-huggingface` | `sys_platform != 'darwin' or platform_machine != 'x86_64'` | sentence-transformers → torch (PR #12469) |
| `docling` (binary) | `sys_platform != 'darwin' or platform_machine != 'x86_64'` | docling-ibm-models → torch (pre-existing) |
| `easyocr` | `sys_platform != 'darwin' or platform_machine != 'x86_64'` | easyocr → torch (pre-existing) |
| `cuga` | `sys_platform == 'darwin' and platform_machine == 'arm64'` | CUDA alternative, ARM64 only on macOS |
| `mlx` | `sys_platform == 'darwin' and platform_machine == 'arm64' and python_version >= '3.12'` | Apple Silicon ML framework |
| `metal` | No marker (correct — cross-platform) | `metal_sdk==2.5.1` is [getmetal.io](https://getmetal.io) cloud SDK, not Apple Metal |

**Extras with NO macOS exclusion that still work on Intel:**

| Extra | Status | Notes |
|-------|--------|-------|
| `docling-core` | ✅ Works | Metadata-only, no torch dependency |
| `ocrmac` | ✅ Works | `sys_platform == 'darwin'` — uses native Vision framework |
| `langchain-unstructured` | ✅ Works | No torch dependency |
| `graph-retriever` | ✅ Works | No platform-specific deps |
| All non-ML extras | ✅ Works | Database, API, monitoring, etc. |

### 2.2 macOS-Specific Runtime Workarounds

| Workaround | Location | Purpose |
|------------|----------|---------|
| `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` | `__main__.py`, `langflow_launcher.py`, CI workflows | Prevents Objective-C fork safety crashes with gunicorn multiprocessing |
| `os.environ["no_proxy"] = "*"` | `__main__.py`, `langflow_launcher.py` | Avoids proxy-related errors with gunicorn on macOS |
| `os.execv()` re-exec pattern | `langflow_launcher.py` | Sets env vars before Objective-C runtime initializes |
| `brew install protobuf` | CI workflow (AMD64 only) | protoc not available on Intel CI runners |

### 2.3 CI Matrix Coverage

| Platform | Python 3.10 | Python 3.12 | Python 3.13 |
|----------|-------------|-------------|-------------|
| macOS ARM64 | ✅ Stable | ✅ Stable | ✅ Experimental |
| macOS AMD64 (Intel) | ✅ Stable | ✅ Stable | ⚠️ Experimental (`continue-on-error`) |
| Linux AMD64 | ✅ Stable | ✅ Stable | ✅ Experimental |
| Windows AMD64 | ✅ Stable | ✅ Stable | ✅ Experimental |

---

## 3. Impact Assessment

### 3.1 What Works on macOS x86_64 Today

Langflow **core functionality** (flow builder, API, database, all non-ML components) works on macOS Intel with Python 3.10–3.13. The following features are **unavailable**:

- ALTK (Agent Lifecycle Toolkit) components
- HuggingFace/sentence-transformers embeddings
- EasyOCR
- Docling document processing (binary; docling-core metadata still works)
- MLX inference
- Metal GPU acceleration
- CUGA

**This is acceptable** because Intel Macs lack the GPU capabilities (Metal 3, Neural Engine) that make these ML features performant.

### 3.2 What Will Break Next

| Timeline | Event | Impact on Langflow |
|----------|-------|--------------------|
| **Now** | PyTorch has no Intel Mac wheels for Python 3.13+ | Already mitigated (PR #12469) |
| **Q3 2026** | GitHub may deprecate `macos-latest-large` (Intel) | Stable CI tests for macOS Intel would need migration or removal |
| **Q4 2026** | macOS 26 (Tahoe) release — potentially last Intel-supporting macOS | Users on Intel Macs stop receiving macOS updates |
| **2027** | macOS 27 drops Intel Mac support | Intel Mac users stuck on macOS 26; system Python/Homebrew may stop building for x86_64 macOS |
| **2027+** | Homebrew, Python.org may drop macOS x86_64 builds | Intel Mac users can't easily install Python 3.14+ |

### 3.3 CI Cost Exposure

`macos-latest-large` (Intel x86_64) is the most expensive runner in the matrix:

- **GitHub Actions pricing:** macOS large runners cost ~$0.12/min (10× Linux)
- **Current usage:** 4 stable jobs + 1 experimental job = 5 Intel Mac CI jobs per workflow run
- **Estimated cost:** ~$15–25 per full CI run for Intel Mac jobs alone

---

## 4. Recommendations

### 4.1 Immediate (No Action Needed)

PR #12469 has already addressed the most critical issue:
- ✅ `altk` and `langchain-huggingface` excluded on macOS x86_64
- ✅ `docling` and `easyocr` already excluded (pre-existing)
- ✅ `mlx`, `cuga` are ARM64-only  
- ✅ Experimental CI uses `continue-on-error: true`

### 4.2 Short-Term (Langflow 1.10 / Q2 2026)

#### ~~R1: Add `platform_machine` marker to `metal` extra~~ — NOT NEEDED

`metal_sdk` is the SDK for [getmetal.io](https://getmetal.io) (a cloud vector search/embedding service), **not** Apple's Metal GPU framework. It's a pure Python package (`py3-none-any.whl`) with no platform-specific dependencies. No marker change needed.

#### R2: Reduce macOS Intel CI to Python 3.12 only

Remove the Python 3.10 stable test on macOS AMD64. Python 3.12 is the most commonly deployed version and provides sufficient coverage:

```yaml
# Remove from stable matrix:
# - os: macos
#   arch: amd64
#   runner: macos-latest-large
#   python-version: "3.10"
```

**Saves:** ~$5–7 per CI run, reduces alert noise.

#### R3: Document macOS support matrix in user-facing docs

Add a support matrix page to `docs/` clarifying which features require Apple Silicon vs. work on Intel, so users have clear expectations.

### 4.3 Medium-Term (Langflow 2.0 / Q4 2026)

#### R4: Drop macOS x86_64 from CI entirely

Once GitHub deprecates `macos-latest-large` or macOS 26 ships:

1. Remove all `macos-latest-large` entries from `cross-platform-test.yml`
2. Remove the `brew install protobuf` step (only needed for Intel runners)
3. Keep `macos-latest` (ARM64) as the sole macOS test target

**Saves:** ~$15–25 per CI run. Reduces matrix complexity.

#### R5: Audit and clean up OBJC fork safety workaround

The `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` workaround in `__main__.py` and `langflow_launcher.py` applies to all macOS, not just Intel. However, once Intel is dropped:
- Verify if the issue persists on Apple Silicon with current gunicorn/uvicorn
- If ARM64-only deployments don't trigger the issue, consider removing the workaround
- If still needed, keep it but document why

#### R6: Officially deprecate macOS x86_64 in release notes

Add a deprecation notice in the Langflow 2.0 release notes:

> **macOS Intel (x86_64) support is deprecated.** Langflow 2.0 is the last version tested on Intel Macs. Future releases will only be tested on Apple Silicon (ARM64). Core functionality may continue to work, but ML features require Apple Silicon.

### 4.4 Long-Term (Langflow 2.x+ / 2027)

#### R7: Remove all macOS x86_64 platform markers

Once Intel Mac support is officially dropped, simplify `pyproject.toml` by removing the `platform_machine != 'x86_64'` guards — they become unnecessary clutter:

```toml
# Before (with Intel exclusion)
altk = ["agent-lifecycle-toolkit>=0.10.1,<1.0; sys_platform != 'darwin' or platform_machine != 'x86_64'"]

# After (Intel dropped from support matrix)
altk = ["agent-lifecycle-toolkit>=0.10.1,<1.0"]
```

#### R8: Evaluate ARM64-only macOS features

With Intel out of the picture, lean into Apple Silicon capabilities:
- MLX-based local inference as a first-class feature
- Metal GPU acceleration for embedding generation
- Neural Engine integration for on-device ML
- CoreML model support via ONNX Runtime CoreML EP

---

## 5. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| GitHub removes `macos-latest-large` runner | High (12–18 months) | CI breaks for Intel tests | R4: Drop Intel from CI proactively |
| User complaints about missing ML features on Intel Mac | Low | User frustration | R3: Document support matrix clearly |
| ~~`metal_sdk` fails on Intel Mac install~~ | N/A | N/A | `metal_sdk` is getmetal.io cloud SDK — cross-platform, no issue |
| Python 3.14 drops macOS x86_64 support | Low (2027+) | Core Langflow broken on Intel | R6: Deprecation notice well in advance |
| OBJC fork safety workaround breaks on new macOS | Low | Server startup crash | R5: Audit and test on macOS 26 |
| Upstream deps (numpy, scipy) drop Intel Mac wheels | Medium (2027+) | Broad installation failures | R6/R7: Official deprecation covers this |

---

## 6. Recommended macOS Support Matrix

### Current (Langflow 1.9.x)

| Feature Category | macOS ARM64 (Apple Silicon) | macOS x86_64 (Intel) |
|-----------------|---------------------------|---------------------|
| Core (flows, API, database) | ✅ Full support | ✅ Full support |
| ML/AI components (ALTK, HuggingFace) | ✅ Full support | ❌ Excluded (no PyTorch wheels) |
| Document processing (Docling, EasyOCR) | ✅ Full support | ❌ Excluded (no PyTorch wheels) |
| Local inference (MLX, MLX-VLM) | ✅ Full support (Python 3.12+) | ❌ Not available (ARM64 only) |
| GPU acceleration (Metal, CUGA) | ✅ Full support | ❌ Not available (ARM64 only) |
| Native OCR (ocrmac) | ✅ Full support | ✅ Full support |

### Proposed (Langflow 2.0+)

| Feature Category | macOS ARM64 (Apple Silicon) | macOS x86_64 (Intel) |
|-----------------|---------------------------|---------------------|
| All features | ✅ Full support | ⚠️ Deprecated — untested, best-effort |

---

## 7. Summary of Action Items

| # | Action | Target Release | Priority | Effort |
|---|--------|---------------|----------|--------|
| — | ~~Exclude `altk` and `langchain-huggingface` on macOS x86_64~~ | ~~1.9.x~~ | ~~Critical~~ | ✅ Done (PR #12469) |
| ~~R1~~ | ~~Add ARM64 marker to `metal` extra~~ | — | — | ❌ N/A (`metal_sdk` is getmetal.io cloud SDK, not Apple Metal) |
| R2 | Remove Python 3.10 macOS Intel from stable CI | 1.10 | Low | 4 lines YAML |
| R3 | Document macOS support matrix for users | 1.10 | Medium | New docs page |
| R4 | Drop macOS x86_64 from CI entirely | 2.0 | Medium | ~20 lines YAML |
| R5 | Audit OBJC fork safety on Apple Silicon | 2.0 | Low | Investigation |
| R6 | Official deprecation notice in release notes | 2.0 | Medium | Release docs |
| R7 | Remove x86_64 platform markers from pyproject.toml | 2.x | Low | Cleanup |
| R8 | Evaluate ARM64-only macOS capabilities | 2.x | Low | Feature planning |

---

## Appendix A: Complete Platform Marker Inventory

All `sys_platform` and `platform_machine` markers in `src/backend/base/pyproject.toml`:

```
Line  53: jq         → sys_platform != 'win32'
Line  96: ocrmac     → sys_platform == 'darwin'                    (root pyproject.toml)
Line 258: metal      → (no marker — correct; getmetal.io cloud SDK, not Apple Metal)
Line 293: altk       → sys_platform != 'darwin' or platform_machine != 'x86_64'
Line 297: langchain-huggingface → sys_platform != 'darwin' or platform_machine != 'x86_64'
Line 310: docling    → sys_platform != 'darwin' or platform_machine != 'x86_64'
Line 312: easyocr    → sys_platform != 'darwin' or platform_machine != 'x86_64'
Line 327: cuga       → sys_platform != 'darwin' (non-Mac) + sys_platform == 'darwin' and platform_machine == 'arm64' (Mac ARM)
Line 331: mlx        → sys_platform == 'darwin' and platform_machine == 'arm64' and python_version >= '3.12'
Line 345: gassist    → sys_platform == 'win32'
```

## Appendix B: Related Issues & PRs

| Reference | Description | Status |
|-----------|-------------|--------|
| LE-172 | PyTorch macOS x86_64 + Python 3.13 CI failure | ✅ Resolved (PR #12469) |
| LE-265 | Broader deprecated macOS support investigation | This document |
| [pytorch/pytorch#114602](https://github.com/pytorch/pytorch/issues/114602) | PyTorch RFC: Deprecate macOS x86_64 builds | Implemented |
| PR #12469 | Exclude torch-dependent extras on macOS x86_64 | Merged/Open |
