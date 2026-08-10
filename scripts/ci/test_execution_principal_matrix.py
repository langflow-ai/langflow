from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_execution_principal_matrix import DEFAULT_MATRIX, REQUIRED_DIMENSIONS, validate_matrix


def test_execution_principal_matrix_is_complete() -> None:
    assert validate_matrix() == []


def test_every_entrypoint_declares_each_principal_and_safety_dimension() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))

    for entrypoint in matrix["entrypoints"]:
        assert set(entrypoint) >= REQUIRED_DIMENSIONS
        assert entrypoint["test_references"]


def test_checker_rejects_a_missing_error_policy(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0].pop("error_policy")
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    assert any("error_policy" in error and "missing" in error for error in validate_matrix(incomplete))
