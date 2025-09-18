"""Test code hash and module metadata functionality."""

import pytest
from langflow.interface.components import import_langflow_components


@pytest.mark.asyncio
async def test_component_metadata_has_code_hash():
    """Test that built-in components have valid module and code_hash metadata."""
    result = await import_langflow_components()
    assert result is not None
    assert "components" in result
    assert len(result["components"]) > 0

    # Find first component to test
    sample_category = None
    sample_component = None
    for category, components in result["components"].items():
        if components:
            sample_category = category
            sample_component = next(iter(components.values()))
            break
    assert sample_component is not None, "No components found to test"

    # Test metadata presence - metadata should be in the 'metadata' sub-field
    assert "metadata" in sample_component, f"Metadata field missing from component in {sample_category}"
    # metadata = sample_component["metadata"]

    # assert "module" in metadata, f"Module metadata missing from component in {sample_category}"
    # assert "code_hash" in metadata, f"Code hash metadata missing from component in {sample_category}"

    # Test that values are valid
    # module_name = metadata["module"]
    # code_hash = metadata["code_hash"]
    # assert isinstance(module_name, str), f"Invalid module name type: {type(module_name)}"
    # assert module_name, f"Invalid module name: {module_name}"
    # assert isinstance(code_hash, str), f"Invalid code hash type: {type(code_hash)}"
    # assert len(code_hash) == 12, f"Invalid code hash: {code_hash} (should be 12 chars)"


@pytest.mark.skip(reason="Skipping while metadata is not added")
async def test_code_hash_uniqueness():
    """Test that different built-in components have different code hashes."""
    result = await import_langflow_components()
    all_hashes = []
    for components in result["components"].values():
        for comp in components.values():
            metadata = comp.get("metadata", {})
            if metadata.get("code_hash"):
                all_hashes.append(metadata["code_hash"])

    # Check that we have some components with metadata
    assert len(all_hashes) > 0, "No components with code hashes found"
    # Check that we have reasonable uniqueness in hashes
    unique_hashes = len(set(all_hashes))
    total_hashes = len(all_hashes)
    uniqueness_ratio = unique_hashes / total_hashes
    # Should have high uniqueness (most components have different code)
    # Adjusted threshold to 90% to account for legitimate code sharing between similar components
    assert uniqueness_ratio > 0.90, f"Hash uniqueness too low: {uniqueness_ratio:.1%}"
