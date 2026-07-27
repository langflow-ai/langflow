"""Natural starter topology contract and deferred CLI guards."""

from __future__ import annotations

import json

import pytest

from tests.locust.langflow_runtime.flows.defaults import FIXTURES_DIR
from tests.locust.langflow_runtime.flows.natural_adapt import NATURAL_TOPOLOGY, node_types
from tests.locust.langflow_runtime.run import _reject_deferred_profile, main


@pytest.mark.parametrize("shape", sorted(NATURAL_TOPOLOGY))
@pytest.mark.parametrize("mode", ["stubbed", "live"])
def test_natural_fixture_topology(shape: str, mode: str) -> None:
    path = FIXTURES_DIR / f"natural_{shape}__external_{mode}.json"
    assert path.exists(), path
    payload = json.loads(path.read_text(encoding="utf-8"))
    present = node_types(payload)
    missing = NATURAL_TOPOLOGY[shape] - present
    assert not missing, f"{path.name} missing {sorted(missing)}; present={sorted(present)}"


@pytest.mark.parametrize("mode", ["stubbed", "live"])
def test_natural_modes_cover_five_shapes(mode: str) -> None:
    for shape in NATURAL_TOPOLOGY:
        assert (FIXTURES_DIR / f"natural_{shape}__external_{mode}.json").exists()


@pytest.mark.parametrize(
    "profile_ref",
    ["deferred/ensemble_flow", "deferred/ensemble_hitl", "profiles/deferred/ensemble_flow"],
)
def test_deferred_profile_rejected_for_execution(profile_ref: str) -> None:
    with pytest.raises(SystemExit, match="deferred"):
        _reject_deferred_profile(profile_ref)


def test_non_deferred_profile_allowed() -> None:
    _reject_deferred_profile("solos/chat_db")


def test_deferred_profile_alias_rejected_after_resolution() -> None:
    with pytest.raises(SystemExit, match="deferred"):
        main(["dry-run", "--profile", "ensemble_flow"])
