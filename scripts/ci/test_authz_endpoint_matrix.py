from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_authz_endpoint_matrix import (
    DEFAULT_MATRIX,
    REQUIRED_PERSONAS,
    VALID_ACTIONS,
    _parse_matrix_route,
    validate_matrix,
)


def test_authz_endpoint_matrix_matches_every_decorated_route() -> None:
    """Adding a route to a covered module requires an explicit matrix classification."""
    assert validate_matrix() == []


def test_authz_endpoint_matrix_has_required_persona_and_safety_dimensions() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    for contract in matrix["contracts"]:
        assert contract["resource"]
        assert contract["domain"]
        assert contract["privacy"]
        assert contract["side_effects"]
        assert contract["frontend"]
        assert contract["test_references"]
        assert set(matrix["persona_presets"][contract["personas"]]) >= REQUIRED_PERSONAS


@pytest.mark.parametrize("action", sorted(VALID_ACTIONS))
def test_authz_endpoint_matrix_accepts_every_canonical_action(action: str) -> None:
    """Every concrete action remains valid, including deploy/update absent from today's matrix."""
    _route, parsed_action, _access = _parse_matrix_route(
        "api/v1/example.py",
        f"POST|/example|example|{action}|authenticated",
    )
    assert parsed_action == action


def test_authz_endpoint_matrix_rejects_unknown_action() -> None:
    """A typo must fail the release contract instead of becoming an unenforced action."""
    with pytest.raises(ValueError, match="unknown authorization action 'raed'"):
        _parse_matrix_route(
            "api/v1/flows.py",
            "GET|/|read_flows|raed|authenticated",
        )


def test_authz_endpoint_matrix_rejects_a_new_unclassified_route(tmp_path: Path, monkeypatch) -> None:
    """Prove the gate fails rather than silently inheriting a broad family default."""
    source = tmp_path / "api" / "v1" / "flows.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/existing')\n"
        "async def existing(): pass\n"
        "@router.post('/new-protected-route')\n"
        "async def new_protected_route(): pass\n",
        encoding="utf-8",
    )
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "persona_presets": {"canonical_v1": dict.fromkeys(REQUIRED_PERSONAS, "defined")},
                "contracts": [
                    {
                        "family": "test",
                        "source": "api/v1/flows.py",
                        "resource": "flow",
                        "domain": "global",
                        "privacy": "404",
                        "side_effects": "guard first",
                        "frontend": "hide denied controls",
                        "personas": "canonical_v1",
                        "test_references": [
                            "scripts/ci/test_authz_endpoint_matrix.py::test_authz_endpoint_matrix_rejects_a_new_unclassified_route"
                        ],
                        "routes": ["GET|/existing|existing|read|authenticated"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("check_authz_endpoint_matrix.API_ROOT", tmp_path)
    assert any(
        "new_protected_route" in error and "unclassified route" in error for error in validate_matrix(matrix_path)
    )
