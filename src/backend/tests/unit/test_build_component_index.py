"""Tests for the build_component_index.py script.

The script lives in the repository-root ``scripts/`` directory, outside any installed package, so it
is loaded by path. The tests are hermetic: component discovery is stubbed at the
``_load_components_for_index`` seam (the real build imports every lfx component), and the output
path is redirected to ``tmp_path`` so the committed ``lfx/_assets/component_index.json`` is never
written.
"""

import hashlib
import importlib.metadata
import importlib.util
from pathlib import Path
from types import ModuleType

import orjson
import pytest
from lfx.interface.components import _read_component_index

REPO_ROOT = Path(__file__).resolve().parents[4]
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_component_index.py"
# Distinct from every real distribution version, so the index provably takes lfx's version and not
# langflow's (the two currently release in lockstep, which would mask the difference).
FAKE_LFX_VERSION = "0.0.0+component-index-test"
_real_distribution_version = importlib.metadata.version


def _fake_distribution_version(distribution_name: str) -> str:
    if distribution_name == "lfx":
        return FAKE_LFX_VERSION
    return _real_distribution_version(distribution_name)


def _sample_components() -> dict:
    """Unsorted categories and components, plus a dynamic field the build must strip."""
    return {
        "zeta": {"ZetaComponent": {"display_name": "Zeta", "metadata": {"timestamp": "2026-01-01T00:00:00"}}},
        "alpha": {
            "BetaComponent": {"display_name": "Beta", "template": {"code": {"type": "code"}}},
            "AlphaComponent": {"display_name": "Alpha", "template": {}},
        },
    }


def _components_loader(modules_dict: dict):
    """Stand-in for ``_load_components_for_index`` that imports no real components."""

    async def _load_components_for_index() -> dict:
        return {"components": modules_dict}

    return _load_components_for_index


async def _failing_components_loader() -> dict:
    msg = "Cannot import"
    raise ImportError(msg)


@pytest.fixture
def build_module(monkeypatch, tmp_path) -> ModuleType:
    """Load a fresh, hermetic copy of the build script.

    A missing script is a regression, so this fails instead of skipping.
    """
    assert BUILD_SCRIPT_PATH.is_file(), f"build_component_index.py not found at {BUILD_SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("build_component_index", BUILD_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_load_components_for_index", _components_loader(_sample_components()))
    monkeypatch.setattr(module, "COMPONENT_INDEX_PATH", tmp_path / "component_index.json")
    monkeypatch.setattr(importlib.metadata, "version", _fake_distribution_version)
    return module


class TestBuildComponentIndexScript:
    """Tests for the build_component_index.py script."""

    def test_build_script_creates_valid_structure(self, build_module):
        """Test that the build script creates a valid index structure."""
        index = build_module.build_component_index()

        assert set(index) == {"version", "metadata", "entries", "sha256"}
        # lfx's runtime loader discards an index whose version is not the installed lfx version.
        assert index["version"] == FAKE_LFX_VERSION
        assert index["metadata"] == {"num_modules": 2, "num_components": 3}
        # Categories and components come out sorted, each component gains a metadata dict, and the
        # dynamic timestamp field is stripped so dependency updates don't churn the hash.
        assert index["entries"] == [
            [
                "alpha",
                {
                    "AlphaComponent": {"display_name": "Alpha", "metadata": {}, "template": {}},
                    "BetaComponent": {"display_name": "Beta", "metadata": {}, "template": {"code": {"type": "code"}}},
                },
            ],
            ["zeta", {"ZetaComponent": {"display_name": "Zeta", "metadata": {}}}],
        ]
        assert list(index["entries"][0][1]) == ["AlphaComponent", "BetaComponent"]

    def test_build_script_writes_pretty_printed_json(self, build_module):
        """Test that main() writes a pretty-printed, key-sorted index that lfx accepts.

        The output was minified until #11392 switched it to indented JSON, so the committed index
        produces readable diffs and resolvable merge conflicts.
        """
        build_module.main()

        output_path = build_module.COMPONENT_INDEX_PATH
        raw = output_path.read_bytes()
        index = orjson.loads(raw)
        assert raw == orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2) + b"\n"
        assert _read_component_index(str(output_path)) == index, "lfx rejected the index main() wrote"

    def test_build_script_sha256_integrity(self, build_module):
        """Test that SHA256 hash is correctly calculated."""
        index = build_module.build_component_index()

        # The hash covers every field except sha256 itself (metadata included), serialized with
        # OPT_SORT_KEYS: exactly how _read_component_index verifies it.
        unhashed = {key: value for key, value in index.items() if key != "sha256"}
        assert set(unhashed) == {"version", "metadata", "entries"}
        payload = orjson.dumps(unhashed, option=orjson.OPT_SORT_KEYS)
        assert index["sha256"] == hashlib.sha256(payload).hexdigest()

    def test_build_script_fails_on_import_errors(self, build_module, monkeypatch, capsys):
        """Test that an import failure aborts the build instead of writing a partial index."""
        monkeypatch.setattr(build_module, "_load_components_for_index", _failing_components_loader)

        with pytest.raises(RuntimeError, match="Failed to import components: Cannot import") as exc_info:
            build_module.build_component_index()
        assert isinstance(exc_info.value.__cause__, ImportError)

        with pytest.raises(SystemExit) as exit_info:
            build_module.main()
        assert exit_info.value.code == 1
        assert not build_module.COMPONENT_INDEX_PATH.exists()
        assert "Failed to build component index" in capsys.readouterr().err
