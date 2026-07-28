"""Natural starter topology and ensemble profile contracts."""

from __future__ import annotations

import json

import pytest

from tests.locust.langflow_runtime.config.loader import load_profile
from tests.locust.langflow_runtime.flows.defaults import FIXTURES_DIR
from tests.locust.langflow_runtime.flows.natural_adapt import NATURAL_TOPOLOGY, node_types


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


@pytest.mark.parametrize("profile_ref", ["ensembles/ensemble_flow", "ensembles/ensemble_hitl"])
def test_ensemble_profiles_are_supported(profile_ref: str) -> None:
    profile = load_profile(profile_ref)
    assert profile.movement_kind == "suite"
    assert "ensemble" in profile.id
