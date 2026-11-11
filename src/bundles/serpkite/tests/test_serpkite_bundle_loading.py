"""The bundle loads through the extension loader as Langflow discovers it at startup."""

from pathlib import Path

import lfx_serpkite
from lfx.extension import load_extension, validate_extension

ROOT = Path(lfx_serpkite.__file__).parent


def test_bundle_validates_and_loads_both_components():
    assert validate_extension(ROOT).ok
    loaded = load_extension(ROOT, distribution="lfx-serpkite")
    assert loaded.ok, loaded.errors
    assert len(loaded.components) == 2
