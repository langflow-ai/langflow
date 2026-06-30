"""Regression tests for ``update_lf_base_dependency``.

The nightly bump pins base's ``lfx`` dependency to the exact ``==X.Y.0.devN`` so the dev
release resolves down the tree. Base also carries ``lfx[extra]`` references (the relocated
cassio/toolguard features) that are pulled by ``langflow-base[complete]``. If those keep a
``~=X.Y.0`` floor while the bare ``lfx`` dep is pinned to the dev version, the floor
(``>=X.Y.0``) excludes ``X.Y.0.devN`` (PEP 440 dev releases sort *below* the final) and the
resolve becomes unsatisfiable. These tests lock in that all ``lfx`` forms -- bare and with
extras -- get the same exact dev pin.
"""

import re
from pathlib import Path

import pytest
import update_lf_base_dependency as mod


@pytest.fixture
def pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway pyproject whose lfx refs mirror src/backend/base/pyproject.toml."""
    content = (
        "[project]\n"
        "dependencies = [\n"
        '    "lfx~=1.11.0",\n'
        "]\n"
        "\n"
        "[project.optional-dependencies]\n"
        'cassandra = ["lfx[cassandra]~=1.11.0"]\n'
        'toolguard = ["lfx[toolguard]~=1.11.0"]\n'
        'beautifulsoup = ["lfx~=1.11.0"]\n'
    )
    path = tmp_path / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    # The script resolves paths relative to BASE_DIR; point it at tmp_path.
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    return path


def test_pins_bare_and_extras_lfx_to_exact_dev(pyproject: Path) -> None:
    mod.update_lfx_dep_in_base(pyproject.name, "1.11.0.dev26")
    result = pyproject.read_text(encoding="utf-8")

    # Every lfx reference -- bare and with extras -- is pinned to the exact dev version.
    assert '"lfx==1.11.0.dev26"' in result
    assert '"lfx[cassandra]==1.11.0.dev26"' in result
    assert '"lfx[toolguard]==1.11.0.dev26"' in result

    # No `~=` floor survives -- a surviving floor is exactly what makes the nightly
    # resolve unsatisfiable.
    assert "~=" not in result
    # Extras are preserved, never dropped.
    assert "[cassandra]" in result
    assert "[toolguard]" in result


def test_idempotent_on_already_pinned(pyproject: Path) -> None:
    mod.update_lfx_dep_in_base(pyproject.name, "1.11.0.dev26")
    once = pyproject.read_text(encoding="utf-8")
    mod.update_lfx_dep_in_base(pyproject.name, "1.11.0.dev26")
    twice = pyproject.read_text(encoding="utf-8")
    assert once == twice


def test_raises_when_no_lfx_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndependencies = ["langflow-base~=1.11.0"]\n', encoding="utf-8")
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    with pytest.raises(ValueError, match="LFX dependency not found"):
        mod.update_lfx_dep_in_base(path.name, "1.11.0.dev26")


def test_pattern_skips_unrelated_packages(pyproject: Path) -> None:
    """Sibling packages whose names merely start with ``lfx`` must not be repinned."""
    extra = '    "lfx-bundles~=1.11.0",\n    "lfxthing~=1.11.0",\n'
    pyproject.write_text(pyproject.read_text(encoding="utf-8") + extra, encoding="utf-8")
    mod.update_lfx_dep_in_base(pyproject.name, "1.11.0.dev26")
    result = pyproject.read_text(encoding="utf-8")
    # The dedicated `lfx` distribution and its extras are repinned...
    assert '"lfx==1.11.0.dev26"' in result
    # ...but `lfx-bundles` / `lfxthing` keep their own floors untouched.
    assert re.search(r'"lfx-bundles~=1\.11\.0"', result)
    assert re.search(r'"lfxthing~=1\.11\.0"', result)
