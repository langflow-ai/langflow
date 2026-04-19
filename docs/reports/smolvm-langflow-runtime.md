# Using smolvm in the Langflow Runtime

**Status:** Exploratory report
**Date:** 2026-04-19
**Subject:** Evaluating [smolvm](https://github.com/smol-machines/smolvm) as a sandboxed execution backend for Langflow flows.

---

## 1. TL;DR

Langflow's runtime executes user-supplied Python (Custom Components, Python REPL tools, Python Code Structured Tools) with **unrestricted `exec()` against host globals** — full filesystem, network, and `importlib` access. smolvm offers sub-200 ms libkrun/Hypervisor.framework microVMs with network-off-by-default isolation and an OCI image model. Wiring smolvm in as a **pluggable code-execution service** (Langflow already supports this pattern) would convert the most dangerous code paths from "trust the author" to "hardware-isolated, network-deny, allowlisted egress" without changing the component-author UX.

The integration is feasible and the surface area is small (~3 call sites). The main gap is that smolvm currently exposes a CLI and an "Embeddable SDK" advertised in the README but not yet documented; a CLI-driven adapter is the pragmatic v1.

---

## 2. What smolvm provides

Source: <https://github.com/smol-machines/smolvm> (v0.5.19, ~1.8k stars, active).

| Property | Value |
|---|---|
| Isolation | Real hardware virtualization — Hypervisor.framework (macOS), KVM (Linux) |
| VMM | libkrun + libkrunfw kernel |
| Image format | OCI (Docker Hub compatible, no Docker daemon) |
| Cold start | < 200 ms |
| Memory | Elastic via virtio-balloon; default 4 vCPU / 8 GiB |
| Network | **Off by default**; opt-in `--net`; egress allowlist via `--allow-host` / `[network].allow_hosts`; TCP/UDP only |
| Filesystem | Directory-only volume mounts (`./src:/app`) |
| Auth | SSH agent forwarding (`SSH_AUTH_SOCK`) — keys stay on host side of the hypervisor |
| Portability | Pack stateful VMs into a single `.smolmachine` binary |
| Configuration | `Smolfile` (TOML): `image`, `[network]`, `[dev]`, `[auth]` |
| Surface | CLI (`smolvm machine run | create | start | stop | exec`, `smolvm pack create`); README claims "Embeddable SDK — Yes" but bindings are not yet documented |

Key CLI shapes relevant to integration:

```bash
smolvm machine run --image python:3.12-alpine -it -- python -c "..."
smolvm machine create --name lf-comp -s Smolfile
smolvm machine exec --name lf-comp -- python /app/run.py
```

---

## 3. Where Langflow runs user code today

All paths below are in this repo. They were mapped end-to-end so the integration points are concrete.

### 3.1 Graph engine (the orchestrator)

- `src/lfx/src/lfx/graph/graph/base.py:356` — `Graph.async_start()` async generator driving the run.
- `src/lfx/src/lfx/graph/graph/base.py:1438` — `Graph.astep()` dequeues the next vertex.
- `src/lfx/src/lfx/graph/graph/base.py:1534` — `Graph.build_vertex()` cache + build orchestration.
- `src/lfx/src/lfx/graph/vertex/base.py:782` — `Vertex.build()` per-vertex driver.
- `src/lfx/src/lfx/graph/vertex/base.py:701` — `Vertex._build_results()` calls
  `initialize.loading.get_instance_results()`.

### 3.2 Custom Component execution (the unsandboxed hot path)

- `src/lfx/src/lfx/interface/initialize/loading.py:28` — `instantiate_class()` parses vertex code via `eval_custom_component_code()`.
- `src/lfx/src/lfx/interface/initialize/loading.py:306` — `build_custom_component()` awaits the component's `build()`.
- `src/lfx/src/lfx/custom/eval.py:9` — `eval_custom_component_code()` entry.
- `src/lfx/src/lfx/custom/validate.py:248` — `create_class()` parses to AST, prepares globals, and **`exec()`s the class definition into a copy of host globals** (lines 271–278). No RestrictedPython, no seccomp, no subprocess.

### 3.3 User-facing "code tool" components

- `src/lfx/src/lfx/components/utilities/python_repl_core.py:72` — wraps `langchain_experimental.utilities.PythonREPL`; only protection is an import allowlist string.
- `src/lfx/src/lfx/components/tools/python_repl.py:73` — same pattern, wrapped as a `StructuredTool`.
- `src/lfx/src/lfx/components/tools/python_code_structured_tool.py:140` — `exec()`s arbitrary user-supplied tool code into globals after AST-loading imports. No isolation.

### 3.4 Plug-in surface that lets us swap backends

- `src/lfx/src/lfx/services/manager.py:43` — `ServiceManager`. Discovery precedence: **config file > `@register_service` decorator > entry points**. One service per `ServiceType` (singleton), plus multi-adapter registries keyed by string.
- `src/lfx/PLUGGABLE_SERVICES.md` — the documented contract.

This is the natural seam: a `CodeExecutionService` registered here can be selected by config without touching graph code.

---

## 4. Threat model gap that smolvm closes

| Capability today | Risk | smolvm mitigation |
|---|---|---|
| `exec(user_code, globals_copy)` in Custom Components | Read/write host FS, exfiltrate env vars / `.aws`, mount points | Guest FS only; explicit volume mounts |
| Unrestricted `importlib.import_module` | Pull arbitrary deps, exec on import | OCI image is the closed world |
| Outbound HTTP from any component | Data exfil, SSRF against internal services | Network off by default; per-flow allowlist |
| Long-running / runaway CPU in user code | Backend process pinned, no quota | vCPU/memory caps per VM |
| State leaks across runs (module cache, `os.environ` mutation) | Cross-tenant pollution | Per-run ephemeral VM, or per-tenant persistent VM |
| SSH/cloud creds reachable by user code | Credential theft | `--ssh-agent` forwards the socket; keys never enter guest |

---

## 5. Proposed integration

### 5.1 Architecture

Introduce `ServiceType.CODE_EXECUTION` with two implementations:

1. `InProcessCodeExecutionService` — current behavior, default, preserves dev ergonomics.
2. `SmolvmCodeExecutionService` — opt-in via `lfx.toml`:

```toml
[services]
code_execution = "lfx_smolvm.service:SmolvmCodeExecutionService"

[services.code_execution.config]
image = "ghcr.io/langflow/runtime-py312:latest"
default_net = false
allow_hosts = ["api.openai.com", "api.anthropic.com"]
mode = "ephemeral"        # or "persistent-per-flow"
cpus = 2
mem_mib = 1024
```

### 5.2 Where to intercept

The smallest viable change patches one function:

- **`src/lfx/src/lfx/interface/initialize/loading.py:306` (`build_custom_component`)** — instead of calling the component's `build()` in-process, marshal `(component_code, params, inputs)` over the boundary, run inside the VM, and return `(component, build_result, artifact)` reconstructed from the VM's serialized output.

For the explicit code-tool components in §3.3, replace the `PythonREPL` / `exec` calls with a thin `code_exec_service.run(code, allowlist)` call. These are the highest-value, lowest-risk wins because they already represent untrusted-by-design code.

### 5.3 v1 transport (CLI-driven)

Until smolvm publishes Python bindings, drive it via subprocess:

```python
# Ephemeral run, stdin = code, stdout = pickled/JSON result
proc = await asyncio.create_subprocess_exec(
    "smolvm", "machine", "run",
    "--image", cfg.image,
    "--cpus", str(cfg.cpus), "--mem", f"{cfg.mem_mib}M",
    *(["--net"] if needs_net else []),
    *[f"--allow-host={h}" for h in cfg.allow_hosts],
    "--", "python", "/app/runner.py",
    stdin=PIPE, stdout=PIPE, stderr=PIPE,
)
out, err = await proc.communicate(payload)
```

A small `runner.py` baked into the image deserializes the request, executes the user code, and serializes the result + artifacts. Volume-mount a tmpdir for large artifacts to avoid stdio pressure.

### 5.4 Persistent vs ephemeral

- **Ephemeral (`smolvm machine run`)**: best isolation, ~200 ms cold start per vertex. Acceptable for human-in-the-loop builds; painful for graphs with many small vertices.
- **Persistent-per-flow (`smolvm machine create` + `exec`)**: one VM per flow run, vertices `exec` into it. Amortizes start cost, keeps tenant isolation. Recommended default.
- **Persistent-per-tenant**: warmest, but reintroduces cross-vertex state leakage inside the tenant boundary.

### 5.5 Async fit

Langflow is asyncio-native (`Graph.astep`, `Vertex.build`). `asyncio.create_subprocess_exec` integrates cleanly; no thread offload needed beyond the existing `Graph.start()` sync wrapper at `base.py:429`.

---

## 6. Open questions / risks

1. **SDK availability.** The README advertises an embeddable SDK but doesn't document bindings. Worth opening an issue upstream before committing to non-CLI transport.
2. **macOS dev parity.** Hypervisor.framework requires macOS; KVM requires Linux + `/dev/kvm`. Windows dev (WSL2) and CI containers (nested virt) need validation. Fall back to `InProcessCodeExecutionService` when virtualization is unavailable.
3. **Component <-> host data marshaling.** Langflow components return rich Python objects (LangChain `Runnable`, custom classes). The boundary forces serialization — likely cloudpickle with an allowlist, or a typed `Message`/`Data` envelope already used at component boundaries. This is the biggest design question.
4. **Image distribution.** A signed `langflow/runtime-py312` image needs to ship with the langchain/langflow deps the average component imports, or component install latency dominates the 200 ms boot.
5. **Streaming.** Many components stream tokens. Stdout-line streaming through the VM is workable but needs a framing protocol (length-prefixed frames or NDJSON).
6. **Filesystem-touching components.** File loaders, vector stores with on-disk persistence — these need explicit mount policy per component category, not blanket deny.
7. **Observability.** Tracing/logging spans currently propagate via in-process context vars; need to forward `trace_id` across the boundary.

---

## 7. Recommendation

Land in three steps:

1. **Define `ServiceType.CODE_EXECUTION`** and refactor the three call sites in §3 to go through it, with the in-process implementation as default. **No behavior change**, but the seam exists.
2. **Ship `lfx-smolvm` as an optional package** with the CLI-driven adapter, persistent-per-flow mode, and a baseline runtime image. Gate behind config; document the Smolfile/allowlist UX.
3. **Default to smolvm for the "code tool" components** (`python_repl_core`, `python_repl`, `python_code_structured_tool`) once the SDK or stable CLI contract lands — these are the components where users most expect untrusted input and where the isolation upside is unambiguous.

Step 1 is worth doing regardless of smolvm — it cleans up the runtime and unlocks other backends (Firecracker, gVisor, WASM).
