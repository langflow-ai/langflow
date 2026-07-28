"""Preflight dependency / feature checks."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.preflight.health import CheckResult
from tests.locust.langflow_runtime.provision.flows import index_by_id, load_fixture_index

# Protocol family → fixture ids that satisfy it when present in state.
_PROTOCOL_FLOW_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "mcp": ("perf_passthrough", "perf_chat_db_agent"),
    "workflows_sync": (),  # any provisioned workflow fixture is fine
    "workflows_stream": (),
    "workflows_background": (),
    "webhook": ("perf_webhook_passthrough",),
}


def check_dependencies(
    state: dict[str, Any] | None,
    profile_protocols: list[str],
    *,
    flow_selectors: list[str] | None = None,
) -> list[CheckResult]:
    """Verify state contains credentials/flows required by the selected profile."""
    results: list[CheckResult] = []
    if not state:
        results.append(CheckResult(name="dependencies", ok=False, detail="provision state missing"))
        return results

    if not state.get("api_key"):
        results.append(CheckResult(name="api_key", ok=False, detail="api_key missing from state"))
    else:
        results.append(CheckResult(name="api_key", ok=True, detail="ok"))

    if "mcp" in profile_protocols:
        if not state.get("project_id"):
            # Also accept project_id nested under any flow record.
            flows = state.get("flows") if isinstance(state.get("flows"), dict) else {}
            has_project = any(isinstance(row, dict) and row.get("project_id") for row in flows.values())
            if not has_project:
                results.append(CheckResult(name="project_id", ok=False, detail="project_id required for mcp"))
            else:
                results.append(CheckResult(name="project_id", ok=True, detail="ok (from flow record)"))
        else:
            results.append(CheckResult(name="project_id", ok=True, detail="ok"))

    flows = state.get("flows") if isinstance(state.get("flows"), dict) else {}
    selectors = list(flow_selectors or [])

    if selectors:
        missing = [fid for fid in selectors if fid not in flows]
        if missing:
            results.append(
                CheckResult(
                    name="profile_flows",
                    ok=False,
                    detail=f"missing from state.flows: {', '.join(missing)}",
                )
            )
        else:
            results.append(CheckResult(name="profile_flows", ok=True, detail="ok"))

        manifest_entries = index_by_id(load_fixture_index())
        pinned_hashes = state.get("fixture_hashes") if isinstance(state.get("fixture_hashes"), dict) else {}
        stale = [
            fid
            for fid in selectors
            if fid in manifest_entries and pinned_hashes.get(fid) != manifest_entries[fid].get("fixture_sha256")
        ]
        if stale:
            results.append(
                CheckResult(
                    name="fixture_hashes",
                    ok=False,
                    detail=f"missing or stale fixture hashes: {', '.join(stale)}; re-run provision apply",
                )
            )
        else:
            results.append(CheckResult(name="fixture_hashes", ok=True, detail="ok"))

        if any(fid in {"perf_kb_ingest", "perf_kb_retrieve"} or "vector_store_rag" in fid for fid in selectors):
            kb = state.get("kb") if isinstance(state.get("kb"), dict) else {}
            kb_ok = bool(kb.get("name")) and str(kb.get("status") or "").lower() in {
                "ready",
                "completed",
                "succeeded",
            }
            results.append(
                CheckResult(
                    name="knowledge_base",
                    ok=kb_ok,
                    detail="ok" if kb_ok else "seeded ready knowledge base missing from state",
                )
            )

        memory_selectors = [fid for fid in selectors if fid.startswith("natural_memory_chatbot__")]
        if memory_selectors:
            memory_bases = state.get("memory_bases") if isinstance(state.get("memory_bases"), dict) else {}
            missing_memory = [fid for fid in memory_selectors if fid not in memory_bases]
            results.append(
                CheckResult(
                    name="memory_bases",
                    ok=not missing_memory,
                    detail="ok"
                    if not missing_memory
                    else f"missing attached memory bases: {', '.join(missing_memory)}",
                )
            )

        if any(fid.startswith("natural_file_parser_agent__") for fid in selectors):
            natural_file = state.get("natural_file") if isinstance(state.get("natural_file"), dict) else {}
            file_ok = bool(natural_file.get("id") and natural_file.get("path"))
            results.append(
                CheckResult(
                    name="natural_file",
                    ok=file_ok,
                    detail="ok" if file_ok else "uploaded Natural parser file missing from state",
                )
            )
    else:
        # Fall back to protocol-family hints when no selectors are provided.
        for protocol in profile_protocols:
            required = _PROTOCOL_FLOW_REQUIREMENTS.get(protocol)
            if not required:
                continue
            if not any(fid in flows for fid in required):
                results.append(
                    CheckResult(
                        name=f"flow_for_{protocol}",
                        ok=False,
                        detail=f"need one of {list(required)} in state.flows",
                    )
                )
            else:
                results.append(CheckResult(name=f"flow_for_{protocol}", ok=True, detail="ok"))

    return results
