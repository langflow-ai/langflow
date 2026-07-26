"""Preflight dependency / feature checks."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.preflight.health import CheckResult

# Protocol family → fixture ids that satisfy it when present in state.
_PROTOCOL_FLOW_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "mcp": ("perf_passthrough", "perf_ensemble_journey", "MemoryChatbotNoLLM"),
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
