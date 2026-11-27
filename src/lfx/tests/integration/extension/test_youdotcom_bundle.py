"""Verify the You.com extension bundle is packaged and discoverable."""

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension import SLOT_OFFICIAL, load_extension


@pytest.mark.integration
def test_youdotcom_bundle_loads_from_its_manifest() -> None:
    import lfx_youdotcom
    from lfx_youdotcom import (
        YouDotComExtractComponent,
        YouDotComResearchComponent,
        YouDotComSearchComponent,
    )

    package_dir = Path(lfx_youdotcom.__file__).parent
    manifest_path = package_dir / "extension.json"
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-youdotcom"
    assert manifest["lfx"]["compat"] == ["1"]
    assert manifest["bundles"] == [{"name": "youdotcom", "path": "components/youdotcom"}]

    result = load_extension(package_dir, slot=SLOT_OFFICIAL, distribution="lfx-youdotcom")
    assert result.ok, [e.code for e in result.errors]
    by_class = {component.class_name: component for component in result.components}
    assert set(by_class) == {
        "YouDotComExtractComponent",
        "YouDotComResearchComponent",
        "YouDotComSearchComponent",
    }
    for component in by_class.values():
        assert component.bundle == "youdotcom"
        assert component.slot == SLOT_OFFICIAL

    assert by_class["YouDotComSearchComponent"].klass.__name__ == YouDotComSearchComponent.__name__
    assert by_class["YouDotComExtractComponent"].klass.__name__ == YouDotComExtractComponent.__name__
    assert by_class["YouDotComResearchComponent"].klass.__name__ == YouDotComResearchComponent.__name__


@pytest.mark.integration
def test_youdotcom_distribution_exposes_current_component_contracts() -> None:
    from lfx_youdotcom import (
        YouDotComExtractComponent,
        YouDotComResearchComponent,
        YouDotComSearchComponent,
    )

    assert importlib_metadata.version("lfx-youdotcom") == "0.1.0"

    search_inputs = {item.name for item in YouDotComSearchComponent.inputs}
    assert "extraction_mode" in search_inputs
    assert "extraction_formats" in search_inputs
    assert "livecrawl" not in search_inputs
    assert "livecrawl_formats" not in search_inputs

    extract_inputs = {item.name for item in YouDotComExtractComponent.inputs}
    assert extract_inputs == {"api_key", "urls", "formats", "timeout"}
    assert {output.name for output in YouDotComResearchComponent.outputs} == {
        "combined",
        "answer",
        "sources_dataframe",
    }
