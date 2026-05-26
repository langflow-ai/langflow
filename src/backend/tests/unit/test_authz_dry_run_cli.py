"""Tests for ``langflow authz dry-run`` (CLI scenario runner)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path  # noqa: TC003 — used at runtime by the pytest tmp_path fixture annotation

import pytest
from langflow.cli.authz_dry_run import (
    _FLOW_GUARDS,
    DryRunResult,
    StubPolicy,
    _run_all,
    _StubAuthorizationService,
    authz_app,
)
from typer.testing import CliRunner

_ACTOR_COUNT = 3  # alice, bob, carol — see _run_all
_EXPECTED_ROWS = len(_FLOW_GUARDS) * _ACTOR_COUNT


# --------------------------------------------------------------------------- #
# Stub policy
# --------------------------------------------------------------------------- #


def _run(coro):
    """Synchronous wrapper for tests that exercise the async stub directly."""
    return asyncio.run(coro)


def test_stub_allow_all_returns_true_unconditionally():
    """allow-all policy permits every request regardless of context."""
    stub = _StubAuthorizationService(StubPolicy.ALLOW_ALL)
    assert _run(stub.enforce(user_id="u", domain="*", obj="flow:x", act="delete")) is True


def test_stub_deny_non_owner_blocks_non_owner_non_superuser():
    """deny-non-owner: only owners and superusers pass."""
    stub = _StubAuthorizationService(StubPolicy.DENY_NON_OWNER)
    assert (
        _run(
            stub.enforce(
                user_id="alice",
                domain="*",
                obj="flow:x",
                act="read",
                context={"is_superuser": False, "flow_user_id": "alice"},
            )
        )
        is True
    )
    assert (
        _run(
            stub.enforce(
                user_id="bob",
                domain="*",
                obj="flow:x",
                act="read",
                context={"is_superuser": False, "flow_user_id": "alice"},
            )
        )
        is False
    )
    assert (
        _run(
            stub.enforce(
                user_id="carol",
                domain="*",
                obj="flow:x",
                act="delete",
                context={"is_superuser": True, "flow_user_id": "alice"},
            )
        )
        is True
    )


def test_stub_deny_writes_allows_reads():
    """deny-writes: read/execute pass, everything else denied."""
    stub = _StubAuthorizationService(StubPolicy.DENY_WRITES)
    assert _run(stub.enforce(user_id="u", domain="*", obj="flow:x", act="read")) is True
    assert _run(stub.enforce(user_id="u", domain="*", obj="flow:x", act="execute")) is True
    assert _run(stub.enforce(user_id="u", domain="*", obj="flow:x", act="write")) is False
    assert _run(stub.enforce(user_id="u", domain="*", obj="flow:x", act="delete")) is False


def test_stub_owner_only_ignores_superuser():
    """owner-only: only the owner passes, even a superuser is denied."""
    stub = _StubAuthorizationService(StubPolicy.OWNER_ONLY)
    assert (
        _run(
            stub.enforce(
                user_id="alice",
                domain="*",
                obj="flow:x",
                act="write",
                context={"is_superuser": True, "flow_user_id": "alice"},
            )
        )
        is True
    )
    assert (
        _run(
            stub.enforce(
                user_id="carol",
                domain="*",
                obj="flow:x",
                act="read",
                context={"is_superuser": True, "flow_user_id": "alice"},
            )
        )
        is False
    )


def test_stub_batch_enforce_mirrors_enforce():
    """batch_enforce applies enforce to each (obj, act) pair."""
    stub = _StubAuthorizationService(StubPolicy.DENY_WRITES)
    results = _run(
        stub.batch_enforce(
            user_id="u",
            domain="*",
            requests=[("flow:1", "read"), ("flow:2", "write")],
        )
    )
    assert results == [True, False]


# --------------------------------------------------------------------------- #
# Scenario runner
# --------------------------------------------------------------------------- #


def test_run_all_produces_one_row_per_guard_per_actor():
    """Every (guard, actor) pair appears exactly once in the report."""
    rows = asyncio.run(_run_all(StubPolicy.ALLOW_ALL))
    assert len(rows) == _EXPECTED_ROWS


def test_allow_all_policy_yields_no_denials():
    """Under allow-all, no row decision should be 'deny'."""
    rows = asyncio.run(_run_all(StubPolicy.ALLOW_ALL))
    denied = [r for r in rows if r.decision == "deny"]
    assert denied == []
    # Every flow-bearing scenario reports flow:{uuid}, never flow:*.
    flow_obj_rows = [r for r in rows if r.scenario.startswith("read_flow")]
    assert all(":*" not in r.obj for r in flow_obj_rows)


def test_deny_non_owner_denies_bob():
    """Bob (non-owner, non-superuser) is denied wherever an owner is present."""
    rows = asyncio.run(_run_all(StubPolicy.DENY_NON_OWNER))
    bob_rows = [r for r in rows if r.actor.startswith("bob")]
    # Scenarios that carry an owner pointer → bob is denied.
    owner_bearing = [r for r in bob_rows if "flow_id" not in r.scenario or "(new)" not in r.scenario]
    denials = [r for r in owner_bearing if r.decision == "deny"]
    assert denials, "expected at least one deny for bob under deny-non-owner"


def test_owner_override_records_decision_for_alice():
    """Alice owns the flow → owner_override fires on every per-flow scenario."""
    rows = asyncio.run(_run_all(StubPolicy.OWNER_ONLY))
    alice_rows = [r for r in rows if r.actor.startswith("alice") and ":" in r.obj and r.obj != "flow:*"]
    assert alice_rows, "expected per-flow rows for alice"
    assert all(r.decision == "owner_override" for r in alice_rows)


def test_deny_writes_blocks_writes_allows_reads():
    """Under deny-writes, read/execute pass and write/create/delete deny."""
    rows = asyncio.run(_run_all(StubPolicy.DENY_WRITES))
    # Restrict to bob (no owner override, no superuser bypass).
    bob_rows = [r for r in rows if r.actor.startswith("bob")]
    for row in bob_rows:
        if row.action in {"read", "execute"}:
            assert row.decision == "allow", row
        else:
            assert row.decision == "deny", row


def test_domain_is_project_prefixed():
    """The recorded domain uses the project:{uuid} form for in-scope scenarios.

    ``_resolve_flow_domain`` prefers project over workspace because g2
    inheritance is directional — passing the more specific domain lets both
    workspace-scoped and project-scoped grants match. The dry-run CLI passes
    both ids on every scenario, so every audited row resolves to ``project:``.
    """
    rows = asyncio.run(_run_all(StubPolicy.ALLOW_ALL))
    project_rows = [r for r in rows if r.domain.startswith("project:")]
    assert project_rows, "expected at least one row with a project domain"


# --------------------------------------------------------------------------- #
# Typer integration
# --------------------------------------------------------------------------- #


def test_cli_table_output_runs_clean():
    """`langflow authz dry-run` renders without raising.

    When ``authz_app`` has a single command, Typer collapses the subcommand
    namespace, so ``CliRunner`` invokes it without the ``dry-run`` segment.
    The fully-namespaced ``langflow authz dry-run`` path is exercised when the
    parent ``app`` is built — see ``test_cli.py`` for that integration.
    """
    runner = CliRunner()
    result = runner.invoke(authz_app, ["--policy", "allow-all"])
    assert result.exit_code == 0, result.output
    assert "allow-all" in result.output


def test_cli_json_output_is_valid_json(tmp_path: Path):
    """`--json --output FILE` writes a parseable JSON document."""
    runner = CliRunner()
    out = tmp_path / "report.json"
    result = runner.invoke(authz_app, ["--policy", "deny-writes", "--json", "--output", str(out)])
    assert result.exit_code == 0, result.output

    payload = json.loads(out.read_text())
    assert payload["policy"] == "deny-writes"
    assert isinstance(payload["results"], list)
    assert len(payload["results"]) == _EXPECTED_ROWS
    # Every result entry has the expected keys.
    expected_keys = {f.name for f in DryRunResult.__dataclass_fields__.values()}
    assert expected_keys <= set(payload["results"][0].keys())


def test_cli_rejects_unknown_policy():
    """An unknown policy value exits non-zero with a typer error."""
    runner = CliRunner()
    result = runner.invoke(authz_app, ["--policy", "nope"])
    assert result.exit_code != 0


@pytest.mark.parametrize("policy", list(StubPolicy))
def test_cli_runs_for_every_built_in_policy(policy: StubPolicy):
    """Every built-in policy produces a clean run."""
    runner = CliRunner()
    result = runner.invoke(authz_app, ["--policy", policy.value])
    assert result.exit_code == 0, result.output
