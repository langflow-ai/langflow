# Manual Test Plan — FileSystem Tool User Isolation

This guide walks you through verifying the L1+L2+L4 user-isolation feature for
the `FileSystemToolComponent`. Every check below maps to a real on-disk artifact
or audit-log line you can inspect; nothing here relies on "the test passed,
trust me".

> **TL;DR:** run `bash CZL/manual_test_quickstart.sh` (created in §0) for the
> automated path. The rest of this document is the hands-on walkthrough.

---

## 0 — One-shot automated verification

If you just want to confirm everything works end-to-end:

```bash
cd src/lfx
uv run python ../../CZL/empirical_isolation_check.py
```

Expected output (last 3 lines):

```
====================================================================
RESULTS: 22 passed, 0 failed
====================================================================
```

The script exits with code 0 only when every isolation guarantee holds. It
walks the temp filesystem after each operation and inspects the audit log line
by line — there is no way for a regression to slip through.

If you also want the unit + integration test suite:

```bash
cd src/lfx
uv run pytest tests/unit/components/tools/ -v
```

Expected: `176 passed`.

---

## 1 — What you are testing

| Layer | Mechanism | What you should see |
|-------|-----------|---------------------|
| **L1** | Per-user namespace under `<base>/users/<hash>/...` | Each user's files live in their own opaque-hashed directory; cross-user reads/lists return structured errors |
| **L2** | Tool-call binding | A `StructuredTool` captured for User A refuses to operate after `_user_id` is changed |
| **L4** | NDJSON audit log | One line per public tool call with `(ts, user_id, flow_id, action, path, ok, err)` |
| **D5** | `.lfsig` reserved | All read/write/glob/grep targeting `.lfsig/...` is rejected |
| **D2** | `mode=on` enforcement | Anonymous calls refused with a structured error |

---

## 2 — Environment variables (cheat sheet)

```bash
# Mode (default: auto)
export LANGFLOW_FS_TOOL_USER_ISOLATION=auto    # off | auto | on

# Where the per-user namespaces live (default: ~/.langflow/fs_tool/fs_sandbox)
export LANGFLOW_FS_TOOL_BASE_DIR=/var/lfx/fs

# Where the HMAC pepper lives (default: ~/.langflow/fs_tool/.fs_pepper).
# Auto-generated 32 random bytes, mode 0600 on POSIX.
export LANGFLOW_FS_TOOL_PEPPER_PATH=/var/lfx/fs/.pepper

# NDJSON audit log (default: disabled / empty = disabled)
export LANGFLOW_FS_TOOL_AUDIT_LOG=/var/lfx/fs/audit.jsonl
```

**Mode semantics:**
- `off` — legacy. Nothing changes vs. the merged PR.
- `auto` (default) — apply isolation when a `user_id` is wired in, fall back
  to legacy when the call is anonymous. Safe default for OSS / desktop.
- `on` — hard. Anonymous calls are refused.

---

## 3 — Walkthrough (hands-on)

### 3.1 Set up an isolated playground

```bash
mkdir -p /tmp/lfx_iso/{base,logs}
export LANGFLOW_FS_TOOL_USER_ISOLATION=auto
export LANGFLOW_FS_TOOL_BASE_DIR=/tmp/lfx_iso/base
export LANGFLOW_FS_TOOL_PEPPER_PATH=/tmp/lfx_iso/base/.pepper
export LANGFLOW_FS_TOOL_AUDIT_LOG=/tmp/lfx_iso/logs/audit.jsonl
cd /Users/criszl/Documents/langflow-support/langflow/src/lfx
```

### 3.2 Have User Alice write a file

```bash
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-alice"
print(c._write_file("plans.md", "ALICE SECRET PLANS"))
PY
```

**Expected:** `{'status': 'created', 'path': 'plans.md', 'bytes_written': 18}`

**Verify on disk:**
```bash
find /tmp/lfx_iso/base -type f
```

You should see one file:
```
/tmp/lfx_iso/base/.pepper
/tmp/lfx_iso/base/users/<32-hex-chars>/plans.md
```

The 32 hex chars are an HMAC of `"user-alice"` keyed with the pepper. They are
not derived from the username in any way an outside observer could reverse.

### 3.3 Have User Bob try to read Alice's file

```bash
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-bob"
print(c._read_file("plans.md"))
PY
```

**Expected:** `{'error': 'File not found: plans.md', 'path': 'plans.md'}`

Bob's namespace is a different hash, so the file is not in his sandbox.

```bash
ls /tmp/lfx_iso/base/users/
```

Expect **two** distinct hex directories (one per user). Both are 32 chars
long — no PII, no identifying information.

### 3.4 Have User Bob list everything

```bash
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-bob"
print(c._glob_search("**/*"))
PY
```

**Expected:** matches list is empty:
```
{'status': 'ok', 'pattern': '**/*', 'matches': [], 'truncated': False, ...}
```

### 3.5 Have User Bob try to escape via path traversal

```bash
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-bob"
print(c._read_file("../../../plans.md"))
print(c._read_file("/etc/passwd"))
PY
```

**Expected:** both return structured errors. The boundary check rejects any
candidate path that doesn't resolve under the user's namespace root.

### 3.6 Confirm the reserved directory is blocked

```bash
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-alice"
print(c._read_file(".lfsig/anything"))
print(c._write_file(".lfsig/poison.json", "{}"))
PY
```

**Expected:** both return structured errors mentioning `reserved` /
`'.lfsig'`. This holds open the future L3 (HMAC sidecar) hook — agents and
users cannot pre-poison the directory.

### 3.7 Inspect the audit log

```bash
cat /tmp/lfx_iso/logs/audit.jsonl
```

You should see one JSON object per line — the records from §3.2 through §3.6:

```json
{"ts":1715000000.123,"user_id":"user-alice","flow_id":null,"action":"write_file","path":"plans.md","ok":true,"err":null}
{"ts":1715000000.456,"user_id":"user-bob","flow_id":null,"action":"read_file","path":"plans.md","ok":false,"err":"File not found: plans.md"}
{"ts":1715000000.789,"user_id":"user-bob","flow_id":null,"action":"glob_search","path":null,"ok":true,"err":null}
...
```

Each record carries the user_id of the caller — operators can answer "who
read which file" forensically without enabling debug logging.

### 3.8 Verify Layer-2 (tool-call binding)

```bash
uv run python - <<'PY'
import asyncio, json
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
c._user_id = "user-alice"
c._write_file("doc.txt", "alice file")
tools = asyncio.run(c._get_tools())
read_tool = next(t for t in tools if t.name == "read_file")

# Switch identity AFTER capturing the tool.
c._user_id = "user-bob"
print(json.loads(read_tool.func("doc.txt")))
PY
```

**Expected:**
```
{'error': 'tool/user-id mismatch: this tool was bound to a different user session and cannot be reused'}
```

This is the defense for the rare-but-real bug class where a captured tool gets
called after the host component has been reused for a different session.

### 3.9 Verify mode=on refuses anonymous calls

```bash
export LANGFLOW_FS_TOOL_USER_ISOLATION=on
uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
c = FileSystemToolComponent(root_path="", read_only=False)
# No _user_id set on purpose — this is the anonymous case.
print(c._read_file("anything"))
PY
```

**Expected:**
```
{'error': 'FileSystemTool requires an authenticated user (LANGFLOW_FS_TOOL_USER_ISOLATION=on)', 'path': 'anything'}
```

This is the gate that lets Astra Cloud re-enable the component.

---

## 4 — Backwards-compatibility check (legacy mode)

Confirm the merged PR's behavior is preserved when isolation is `off`:

```bash
unset LANGFLOW_FS_TOOL_USER_ISOLATION
unset LANGFLOW_FS_TOOL_BASE_DIR
export LANGFLOW_FS_TOOL_USER_ISOLATION=off

mkdir -p /tmp/lfx_legacy
echo "legacy hello" > /tmp/lfx_legacy/hello.txt

uv run python - <<'PY'
from lfx.components.tools.filesystem import FileSystemToolComponent
# No user_id wired — the existing 116 tests in the merged PR pass like this.
c = FileSystemToolComponent(root_path="/tmp/lfx_legacy", read_only=False)
print(c._read_file("hello.txt"))
PY
```

**Expected:** `{'status': 'ok', ..., 'content': '     1→legacy hello'}`.

The 116 unit tests from PR #12901 are still part of the test suite and stay
green — see §0.

---

## 5 — Cleanup

```bash
unset LANGFLOW_FS_TOOL_USER_ISOLATION LANGFLOW_FS_TOOL_BASE_DIR LANGFLOW_FS_TOOL_PEPPER_PATH LANGFLOW_FS_TOOL_AUDIT_LOG
rm -rf /tmp/lfx_iso /tmp/lfx_legacy
```

---

## 6 — How to interpret a failure

If any check above fails, capture:

1. The exact env-var values in your shell (`env | grep LANGFLOW_FS_TOOL_`).
2. The on-disk tree (`find $LANGFLOW_FS_TOOL_BASE_DIR -maxdepth 4`).
3. The full audit log (`cat $LANGFLOW_FS_TOOL_AUDIT_LOG`).
4. The exact command and Python version (`uv run python --version`).

Common pitfalls:

| Symptom | Likely cause |
|---------|--------------|
| Two different users land under the same hash | The pepper file was lost mid-test — check `LANGFLOW_FS_TOOL_PEPPER_PATH` mode is 0600 and that no other process truncates it |
| Audit log empty | `LANGFLOW_FS_TOOL_AUDIT_LOG` is unset or empty (treated as disabled). Set it explicitly. |
| `'error': 'root_path is required'` even with mode=auto | The user_id resolved to None; check `_user_id` was set on the component instance |
| Files appear at literal `<base>/<sub_path>` (no `users/` prefix) | Mode is `off` or fell back to legacy — confirm `_user_id` is non-empty and not the literal string `"None"` |

---

## 7 — Layers NOT covered by this rollout

The plan in `FILESYSTEM_USER_ISOLATION_PLAN.md` describes five layers. This
implementation ships **L1 + L2 + L4 + the `.lfsig` reservation**. The
following are explicit follow-ups:

- **L3 — HMAC content signatures.** Per-file `.lfsig/<path>.sig` sidecars and
  a `require_signed=True` strict-read mode. The reserved segment is already
  blocked, so the L3 follow-up is a pure additive change.
- **L5 — Per-user allowlist override** via `LANGFLOW_FS_TOOL_PER_USER_ROOTS`
  JSON env var.
- **Migration tool** (`langflow fs-migrate`) for moving an existing single-tenant
  sandbox into the per-user namespace layout.

These do not affect the security guarantees of L1+L2+L4 — they extend them.
