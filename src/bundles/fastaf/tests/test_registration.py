"""Manifest, editable discovery and real loader contract for this new bundle."""

import inspect
import json
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import lfx_fastaf
from lfx.extension import SLOT_OFFICIAL, load_extension
from lfx.extension.loader._plugins import installed_extension_roots


def test_distribution_ships_matching_manifest_and_entry_point():
    root = Path(lfx_fastaf.__file__).parent
    manifest = json.loads((root / "extension.json").read_text())
    distribution = metadata.distribution("lfx-fastaf")
    assert manifest["id"] == "lfx-fastaf"
    assert manifest["version"] == distribution.version
    assert manifest["lfx"]["compat"] == ["1"]
    assert manifest["bundles"] == [{"name": "fastaf", "path": "components/fastaf"}]
    assert any(ep.group == "langflow.extensions" and ep.value == "lfx_fastaf" for ep in distribution.entry_points)
    assert installed_extension_roots()["lfx-fastaf"] == root


def test_loader_registers_exactly_ten_runnable_components_without_network():
    root = Path(lfx_fastaf.__file__).parent
    with patch("lfx_fastaf._base.httpx.stream") as stream:
        result = load_extension(root, slot=SLOT_OFFICIAL, distribution="lfx-fastaf")
        assert result.ok, [error.code for error in result.errors]
        by_class = {item.class_name: item for item in result.components}
        assert sorted(by_class) == sorted(lfx_fastaf.__all__)
        for class_name in lfx_fastaf.__all__:
            loaded = by_class[class_name]
            assert loaded.bundle == "fastaf"
            assert loaded.slot == SLOT_OFFICIAL
            assert inspect.getsourcefile(loaded.klass) == inspect.getsourcefile(getattr(lfx_fastaf, class_name))
            instance = loaded.klass()
            assert callable(getattr(instance, instance.outputs[0].method))
    stream.assert_not_called()
