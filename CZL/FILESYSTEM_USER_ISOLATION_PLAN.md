# FileSystem Tool — Per-User Isolation & Signing Plan

Follow-up hardening proposal for the `FileSystemToolComponent` shipped in
[PR #12901](https://github.com/langflow-ai/langflow/pull/12901).

> **Goal:** make it impossible for a flow run by user **A** to read, list, write,
> or modify files that belong to user **B**, even when both users execute the
> same flow on the same Langflow instance with the same `root_path`.

---

## 1. Executive Summary

The merged feature sandboxes file I/O to a flow-level `root_path` and adds an
operator-controlled global allowlist (`LANGFLOW_FS_TOOL_ALLOWED_ROOTS`). It is
correct for **single-tenant** OSS / desktop deployments and is explicitly disabled
in Astra Cloud — because in any shared / multi-user deployment two distinct
authenticated users sharing the same `root_path` see each other's files.

This plan closes that gap with a **layered defense**:

| Layer | Mechanism | Defends Against |
|---|---|---|
| **L1** (mandatory) | Per-user namespace auto-derived from `self.user_id` | A reading B's files via the same flow |
| **L2** (mandatory) | Tool-call binding: each `StructuredTool` closure captures `user_id` at build time and re-checks at call time | Tool reuse across user contexts, late-binding races |
| **L3** (optional) | HMAC sidecar manifest: every write records `path → user_id, sig(content, user_secret)` | Externally-placed files, tampering, file injection from outside the tool |
| **L4** (always-on) | Structured audit log: `(user_id, flow_id, action, path, ts, ok/err)` | Forensics, compliance, anomaly detection |
| **L5** (operator) | Per-user allowlist override via JSON-shaped env var | Power users / heterogeneous tenants needing specific carve-outs |

**Required L1 + L2 are sufficient to flip Astra Cloud back on**. L3 is needed
only when operators want cryptographic integrity guarantees (e.g., regulated
environments). L4 is cheap and should ship from day one.

---

## 2. Current State Analysis

### 2.1 What the component already has
- Strong path validation (`_validate_path`): NUL-byte rejection, Windows
  portability, `resolve()` + `is_relative_to()` boundary check — catches
  `../` traversal **and** symlink escapes (`src/lfx/src/lfx/components/tools/filesystem.py:404`).
- Operator gates: cloud disable (`is_astra_cloud_environment()`) and global
  `LANGFLOW_FS_TOOL_ALLOWED_ROOTS` allowlist (`filesystem.py:368`).
- Resource caps: 10 MB per file, 100-result glob ceiling, ReDoS guard, regex
  scan ceilings.
- Structured error envelopes (no exceptions leak to the agent).

### 2.2 What it is missing
- **No user identity awareness.** The component does not consult `self.user_id`
  at any point. The `Component` base class **already populates `self._user_id`**
  during `instantiate_class()` (see `src/lfx/src/lfx/interface/initialize/loading.py:46`)
  and exposes it via `self.user_id` (cascades through `self.graph.user_id`).
  We get this attribute for free; we just have to use it.
- **No per-tool-call binding.** `StructuredTool` closures capture `self`, so if
  the component instance is reused across user contexts (in-process pooling,
  background tasks), every captured tool would inherit whichever user_id was
  last set. Today this isn't exploited because identity isn't used at all — the
  moment we add it, this becomes a real concern.
- **No file-level ownership.** Anything dropped into the sandbox by another
  process (cron job, sidecar container, mount) is indistinguishable from a
  legitimate user file. There is no detection of files placed outside the tool.
- **No audit trail.** Operators cannot answer "who read `/data/secrets.txt` last
  Tuesday?".

### 2.3 Threat model — concrete scenarios

| # | Attacker | Today's outcome | Plan mitigates with |
|---|---|---|---|
| T1 | User B runs a flow with `root_path=/workspaces` after user A wrote `/workspaces/A_notes.md` | B reads A's file | L1 |
| T2 | Flow author hard-codes `root_path=/`, deploys to a multi-tenant instance | All users share full FS view | L1 (forces a `/<user_id>/` suffix) + L5 |
| T3 | A malicious cron job writes `/sandbox/<user_id>/evil.json` | Tool reads it as if the user wrote it | L3 (signature mismatch) |
| T4 | A holds a long-lived agent session; B's flow runs concurrently and the worker reuses A's `FileSystemToolComponent` instance | B's call uses A's user_id | L2 (per-tool-call re-check) |
| T5 | A symlinks `/sandbox/<A>/link` → `/sandbox/<B>/secret` | Already blocked by `is_relative_to` boundary | (existing) |
| T6 | A writes a 10 MB file then claims B did it | No way to know who wrote what | L3 + L4 |
| T7 | An operator forgets to set `LANGFLOW_FS_TOOL_ALLOWED_ROOTS` on a SaaS deploy | All users get free-form root_path | L1 makes the global allowlist redundant for cross-user isolation |

---

## 3. Proposed Architecture

### 3.1 Core idea — derive the effective sandbox from identity

Replace the single resolution step:
```
effective_root = resolve(root_path)
```
with:
```
effective_root = resolve(base_root) / "users" / sha256(user_id)[:32] / resolve(sub_path)
```

The user-supplied `root_path` is reinterpreted as a **sub-path inside the user's
private namespace**, not as the absolute base. The base is operator-controlled;
the user namespace is identity-controlled; the sub-path is flow-author-controlled.
None of the three alone can reach another user's files.

This is the single most important change. Everything else is defense in depth.

### 3.2 Why a hash, not raw `user_id`

- `user_id` is a UUIDv4 in Langflow today — already opaque, already URL-safe.
- However, the directory listing of `/sandbox/users/` would reveal the set of
  users who have ever used the tool. Hashing with a server-side pepper
  (`LANGFLOW_FS_TOOL_NAMESPACE_PEPPER`, generated on first boot) prevents this
  enumeration leak.
- Truncating to 32 hex chars (128 bits) keeps the path readable while leaving
  zero practical collision risk.

### 3.3 Why HMAC sidecar (L3) instead of xattrs or DB rows

| Mechanism | Pros | Cons | Verdict |
|---|---|---|---|
| Linux `xattr` | Fast, kernel-enforced | Filesystem-dependent (tmpfs, NFS, FAT lose them); breaks on macOS/Windows parity | **Reject** — Langflow targets all three OSes |
| Per-file `.sig` sidecar | Portable, simple to verify, survives `cp`/`mv` | Doubles file count in directory listings | **Use** but hide via `.lfsig/` shadow tree |
| DB row per file | Transactional, queryable | Out-of-band file changes desync; adds schema migration; cross-process coupling | **Reject** — keeps the component self-contained |
| Manifest file `.lfsig/manifest.json` | Single small file per user, atomic rewrite | Locking on concurrent writes | **Use** for the audit index; per-file sidecars for content sigs |

Decision: **per-file sidecar for content HMAC** (covers integrity), **per-user
manifest** (covers existence — "this file was created by me at time T").

### 3.4 Why per-tool-call binding (L2)

When `_get_tools()` returns a `StructuredTool`, the closure captures `self`.
If the component instance is reused (today's runtime path doesn't pool, but
background-task changes or the upcoming worker pool will), every tool already
issued sees whichever `user_id` is currently on the instance. Capture-and-check:

```python
def _make_read_tool(self) -> StructuredTool:
    bound_user_id = self.user_id  # captured at build time
    def _run(path: str, ...) -> str:
        if self.user_id != bound_user_id:
            return json.dumps({"error": "tool/user-id mismatch (bound to a different session)"})
        return json.dumps(self._read_file(path, ...))
    ...
```

Cheap, eliminates a whole class of bugs that L1 alone would not catch.

---

## 4. Detailed Design

### 4.1 Inputs (component config)

Add **one** required-feeling but optional input plus one operator switch:

```python
inputs = [
    StrInput(
        name="root_path",
        display_name="Sub-path",
        required=False,                         # was True
        info="Path inside YOUR private workspace. Empty = workspace root.",
    ),
    BoolInput(
        name="read_only",
        display_name="Read Only",
        value=False,
        advanced=True,
    ),
    # NEW — exposed only when LANGFLOW_FS_TOOL_USER_ISOLATION != "off"
    BoolInput(
        name="require_signed",
        display_name="Reject Unsigned Files",
        value=False,
        advanced=True,
        info=(
            "If true, reads fail when the file has no valid HMAC sidecar. "
            "Use for high-integrity workspaces."
        ),
    ),
]
```

Rename `root_path` → `sub_path` in the UI label (keep the field name for
backwards compatibility) so the operator's mental model lines up with the new
semantics.

### 4.2 Operator-controlled environment

| Var | Default | Effect |
|---|---|---|
| `LANGFLOW_FS_TOOL_USER_ISOLATION` | `auto` | `auto`=on when user is authenticated, off for anonymous; `on`=hard required, anonymous flows are refused; `off`=legacy single-tenant behavior |
| `LANGFLOW_FS_TOOL_BASE_DIR` | `<config_dir>/fs_sandbox` | Absolute base under which `users/<hash>/` namespaces live |
| `LANGFLOW_FS_TOOL_NAMESPACE_PEPPER` | auto-generated and persisted in `<config_dir>/.fs_pepper` on first boot | HMAC key for the user→hash mapping |
| `LANGFLOW_FS_TOOL_SIGNING_KEY` | auto-generated and persisted | HMAC key for content signatures (rotation-aware: keep last N keys) |
| `LANGFLOW_FS_TOOL_PER_USER_ROOTS` | unset | JSON `{"<user_id>": ["/path1", "/path2"]}` to override the default `<base>/users/<hash>` namespace per user |
| `LANGFLOW_FS_TOOL_ALLOWED_ROOTS` | unset | (existing) global allowlist — kept for backwards compatibility and for `isolation=off` mode |
| `LANGFLOW_FS_TOOL_AUDIT_LOG` | `<config_dir>/fs_audit.jsonl` | NDJSON sink for L4 audit events |

Setting `LANGFLOW_FS_TOOL_USER_ISOLATION=on` is what flips Astra Cloud back on.

### 4.3 Identity resolution (`_resolve_identity`)

```python
def _resolve_identity(self) -> str:
    """Return the validated user_id or raise. Single point of truth."""
    mode = os.environ.get("LANGFLOW_FS_TOOL_USER_ISOLATION", "auto").lower()
    if mode == "off":
        return ""                                # legacy mode — no namespace prefix
    user_id = getattr(self, "user_id", None)
    if not user_id:
        if mode == "on":
            raise PermissionError("FileSystemTool requires an authenticated user")
        return ""                                # auto + anonymous → legacy
    return str(user_id)
```

### 4.4 Namespace derivation (`_user_namespace`)

```python
def _user_namespace(self, user_id: str) -> Path:
    """Stable, opaque, collision-free directory name per user."""
    if not user_id:
        return Path("")                          # legacy mode shortcut
    pepper = _load_or_create_pepper()
    digest = hmac.new(pepper, user_id.encode(), hashlib.sha256).hexdigest()[:32]
    return Path("users") / digest
```

### 4.5 Effective root (`_validate_root`, replaced)

```python
def _validate_root(self) -> Path:
    if is_astra_cloud_environment() and os.environ.get(
        "LANGFLOW_FS_TOOL_USER_ISOLATION", "auto"
    ).lower() != "on":
        raise PermissionError("FileSystemTool requires user isolation in cloud deployments")

    user_id = self._resolve_identity()
    base = Path(os.environ.get("LANGFLOW_FS_TOOL_BASE_DIR") or _default_base()).resolve()
    namespace = self._user_namespace(user_id)
    sub = (self.root_path or "").strip().lstrip("/\\")          # treat sub_path as relative

    candidate = (base / namespace / sub).resolve()
    user_root = (base / namespace).resolve()
    if not candidate.is_relative_to(user_root):
        raise PermissionError(f"sub_path {self.root_path!r} escapes user namespace")

    # Optional per-user allowlist override (L5)
    overrides = _per_user_overrides(user_id)
    if overrides is not None and not any(candidate.is_relative_to(o) for o in overrides):
        raise PermissionError("sub_path is not in this user's allowlist")

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate
```

Note: `mkdir(parents=True, exist_ok=True)` is **safe under L1** because the
candidate is guaranteed under `user_root`, and the operator owns `base`.

### 4.6 Tool binding (L2)

In each `_make_*_tool`, capture `bound_user_id = self.user_id` outside the
closure and re-check inside. Add a single helper to keep the five tool factories
honest:

```python
def _bind(self, fn):
    bound_user_id = self.user_id
    def _wrapped(*args, **kwargs):
        if self.user_id != bound_user_id:
            return json.dumps({"error": "tool/user-id mismatch"})
        return fn(*args, **kwargs)
    return _wrapped
```

### 4.7 HMAC sidecar (L3) — only when `require_signed=True` or on every write

Layout (hidden under a single dot-prefixed shadow dir per user namespace):

```
<base>/users/<hash>/
  └── notes/
        └── plan.md
<base>/users/<hash>/.lfsig/
  ├── manifest.jsonl                # one line per write: {path, ts, sha256, sig}
  └── notes/
        └── plan.md.sig             # HMAC(content) for fast per-file verify
```

Sidecars live in a parallel tree to keep ordinary `glob_search`/`grep_search`
clean and prevent the agent from poking at signatures (the path validator
rejects `.lfsig` segments in user-supplied paths — see §4.8).

Verification on read:
1. If `require_signed=True` and no sidecar exists → reject with structured error.
2. If sidecar exists, recompute HMAC over file content; mismatch → reject.
3. If sidecar exists but sig is from a rotated-out key → re-sign with current
   key and continue (operators can rotate without breaking flows).

### 4.8 Path validator additions

Append to `_validate_path`:
```python
if any(part == ".lfsig" for part in candidate.parts):
    raise PermissionError("path is reserved")
```
Keeps the agent and the user out of the signing tree.

### 4.9 Audit log (L4)

Single helper, append-only NDJSON, fsync optional (operator setting):

```python
def _audit(self, action: str, path: str | None, *, ok: bool, err: str | None = None) -> None:
    record = {
        "ts": time.time(),
        "user_id": getattr(self, "user_id", None),
        "flow_id": getattr(self, "flow_id", None),
        "action": action,            # read_file | write_file | edit_file | glob_search | grep_search
        "path": path,
        "ok": ok,
        "err": err,
    }
    _AUDIT_SINK.write(json.dumps(record) + "\n")
```

Shipping this from day one is non-negotiable — it is the only way to detect L1
regressions in production.

---

## 5. Implementation Plan (phased)

The user wants this as a **follow-up to a merged PR**, so phasing matters: the
existing component is in the wild and we cannot break it.

### Phase 1 — Shadow mode (no behavior change)
- Add `_resolve_identity`, `_user_namespace`, audit log helper.
- Wire audit log into all five tools; do **not** change path resolution yet.
- Ship `LANGFLOW_FS_TOOL_USER_ISOLATION=off` as the implicit default.
- Effort: ~1 day. Risk: none. Output: production telemetry for §6.

### Phase 2 — Opt-in isolation (`USER_ISOLATION=auto`)
- Switch `_validate_root` to the new logic when isolation mode is `auto` or `on`
  AND the user is authenticated.
- Migrate existing flows: a one-shot tool (`langflow fs-migrate`) that walks
  the legacy `<root_path>` per known user and copies into
  `<base>/users/<hash>/`, prompting for confirmation per user.
- Add per-tool-call binding (L2).
- Effort: ~3–4 days incl. tests + migration tool.
- Risk: medium — existing single-tenant deploys keep working as long as they do
  not change the env var.

### Phase 3 — Sign-on-write (L3)
- Default to writing sidecars on every successful `write_file` / `edit_file`.
- `require_signed=True` enables strict-read mode.
- Add key rotation support.
- Effort: ~2–3 days incl. tests + key rotation tool.

### Phase 4 — Re-enable in cloud
- Drop the `is_astra_cloud_environment` blanket disable when
  `USER_ISOLATION=on`.
- Astra deploys ship with `USER_ISOLATION=on`, `BASE_DIR=/var/lfx/fs`,
  `SIGNING_KEY` from secret store.
- Coordinate with the cloud team for the rollout flag.

### Phase 5 — Hard-default (next major)
- Flip default to `USER_ISOLATION=auto` for all installs.
- Document migration in release notes.
- Drop the legacy global `LANGFLOW_FS_TOOL_ALLOWED_ROOTS` semantics if telemetry
  shows no usage.

---

## 6. Backwards Compatibility

| Existing behavior | Phase 1 | Phase 2 (`auto`) | Phase 3 | Phase 5 |
|---|---|---|---|---|
| Single-user OSS install | unchanged | unchanged (no `user_id` → legacy path) | unchanged | flipped to namespace; migration tool prompts |
| Multi-user instance with explicit `root_path` | unchanged | now scoped to `<base>/users/<hash>/<root_path>`; pre-existing files require migration | + signing | + signing |
| Astra Cloud | disabled | disabled (until phase 4) | disabled | enabled with `on` mode |
| Flow author hard-coded `/etc/passwd` | rejected by allowlist (if set) | rejected by namespace boundary (always) | same | same |

The migration command MUST be idempotent and dry-run-able. Consider adding a
`--user-id-from-flow-history` mode that walks `flow.user_id` for past runs and
attributes existing files accordingly.

---

## 7. Test Plan

Tests live next to the existing suite at
`src/lfx/tests/unit/components/tools/test_filesystem.py`. Add a new class
`TestUserIsolation` covering:

1. **L1 boundary** — two component instances with different `_user_id`s see
   disjoint trees; `glob_search('**/*')` from A's instance never returns B's
   files even when both wrote the same `path`.
2. **Namespace stability** — same `user_id` + same pepper → same hash across
   process restarts; different pepper → different hash.
3. **Anonymous + `mode=on`** — refused with structured error.
4. **Anonymous + `mode=auto`** — falls back to legacy single-tenant.
5. **Tool binding (L2)** — mutate `self._user_id` after `_get_tools()` returns,
   then call a captured tool — must error with `tool/user-id mismatch`.
6. **Sidecar present + content tampered** — read fails with signature error.
7. **Sidecar absent + `require_signed=True`** — read fails.
8. **Sidecar absent + `require_signed=False`** — read succeeds, audit logs
   `unsigned=true`.
9. **`.lfsig` reserved** — agent attempting to read/write/glob `.lfsig/...`
   returns structured error.
10. **Per-user allowlist override** — JSON env var routes user X to a custom
    path, user Y to default namespace.
11. **Key rotation** — old-key sidecar verifies, gets re-signed; current-key
    sidecar verifies; unknown-key sidecar rejects.
12. **Audit log shape** — every public tool call emits exactly one NDJSON line
    with the documented fields.
13. **Migration tool** — dry-run prints the plan; real run is idempotent;
    re-running on an already-migrated tree is a no-op.
14. **Concurrency** — two threads writing to the same path under the same user
    do not corrupt the manifest (atomic append + lock).

---

## 8. Open Questions / Decisions Needed

1. **Where does the pepper / signing key live?** Proposal: `<config_dir>/.fs_keys.json`,
   chmod 0600, generated on first boot. For Astra: pulled from the existing
   secret manager — needs a lookup contract from the cloud team.
2. **Should `flow_id` participate in the namespace?** I.e.,
   `users/<hash>/<flow_hash>/...`? Pros: scopes per flow too, lets a user
   delete one flow's data without touching another. Cons: doubles the depth,
   complicates cross-flow workflows. **Recommendation: no, keep flow scoping
   as a `sub_path` convention** — the user can pick `flowA/` if they want it.
3. **Sidecar storage cost.** A 1 KB HMAC sidecar per file plus a manifest line
   roughly doubles inode count for tiny-file workloads. Consider a single
   per-directory `_lfsig_index` instead of per-file sidecars if telemetry shows
   this matters.
4. **Cross-user shared workspace.** Some teams will want a shared dir.
   Out of scope for this plan; revisit only after L1–L4 ship and we see the
   demand. The right primitive then is an explicit `shared_paths` env var,
   read-only-by-default, with audit logging on by force.
5. **Identity outside the run loop.** If a tool call ever happens outside a
   graph run (e.g., scheduled tasks, MCP), `self.user_id` is unset. Phase 1
   audit will tell us whether this is a real path; if so, those callers need to
   carry an explicit user identity — they cannot be allowed to fall through to
   legacy mode.
6. **Quotas.** Per-user disk quota is the natural pairing for L1 but is OS-level
   and cluster-dependent. Out of scope for this plan; flag as a follow-up.

---

## 9. TL;DR

Implement **L1 (auto namespace from `self.user_id`) + L2 (tool-call binding) +
L4 (audit log)** in a single follow-up PR, behind
`LANGFLOW_FS_TOOL_USER_ISOLATION=auto`. That alone closes every cross-user
scenario in the threat model and lets Astra Cloud re-enable the component.
**L3 (HMAC sidecar) and L5 (per-user override)** ship as a second PR for
operators who want cryptographic integrity and heterogeneous tenant policies.

Total estimated effort: **5–8 engineering days** plus migration tooling, spread
across two PRs. No schema changes, no new services, no breaking changes for
existing OSS / desktop installs.
