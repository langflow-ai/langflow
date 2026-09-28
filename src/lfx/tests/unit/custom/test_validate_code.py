"""Tests for lfx.custom.validate.validate_code import checking.

H1-3992099: validate_code must locate imports via importlib.util.find_spec()
without executing the imported module's top-level code.
"""

import importlib
import sys
import types

from lfx.custom.validate import validate_code

NO_ERRORS = {"imports": {"errors": []}, "function": {"errors": []}}


def test_validate_code_valid_import():
    errors = validate_code("import math\n\n\ndef square(x):\n    return x ** 2\n")
    assert errors == NO_ERRORS


def test_validate_code_missing_module_reports_error():
    errors = validate_code("import no_such_module_xyz_123\n\n\ndef f():\n    pass\n")
    assert errors == {
        "imports": {"errors": ["No module named 'no_such_module_xyz_123'"]},
        "function": {"errors": []},
    }


def test_validate_code_find_spec_failure_reports_error(monkeypatch):
    """A module present in sys.modules with __spec__ = None makes find_spec() raise ValueError.

    The error must be reported, not propagated.
    """
    module = types.ModuleType("specless_module")
    module.__spec__ = None
    monkeypatch.setitem(sys.modules, "specless_module", module)

    errors = validate_code("import specless_module\n\n\ndef f():\n    pass\n")

    assert errors["function"]["errors"] == []
    assert len(errors["imports"]["errors"]) == 1
    assert "specless_module" in errors["imports"]["errors"][0]


def test_validate_code_does_not_execute_imported_modules(tmp_path, monkeypatch):
    """A module planted on a writable sys.path entry must not run during validation."""
    marker = tmp_path / "planted_module_executed.txt"
    (tmp_path / "planted_validate_rce.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "planted_validate_rce", raising=False)

    errors = validate_code("import planted_validate_rce")

    assert errors == NO_ERRORS
    assert not marker.exists()

    # Control: a real import of the same module DOES execute it.
    importlib.import_module("planted_validate_rce")
    assert marker.exists()


def test_validate_code_does_not_import_parent_packages(tmp_path, monkeypatch):
    """find_spec() on a dotted name would execute parent packages.

    Only the top-level package may be resolved.
    """
    marker = tmp_path / "planted_parent_executed.txt"
    package = tmp_path / "planted_parent_pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    (package / "child.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "planted_parent_pkg", raising=False)

    errors = validate_code("import planted_parent_pkg.child")

    assert errors == NO_ERRORS
    assert not marker.exists()
