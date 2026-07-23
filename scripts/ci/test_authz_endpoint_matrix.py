from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_authz_endpoint_matrix import DEFAULT_MATRIX, REQUIRED_PERSONAS, validate_matrix


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
