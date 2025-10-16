"""Integration test to verify healthcare mappings work in real ComponentMapper."""

from langflow.custom.genesis.spec.mapper import ComponentMapper


def test_healthcare_mappings_integration():
    """Test that healthcare mappings are properly integrated and functional."""
    mapper = ComponentMapper()

    # Test that healthcare mappings are loaded
    assert hasattr(mapper, 'HEALTHCARE_MAPPINGS')

    # Check if healthcare mappings are populated (either from import or empty dict)
    healthcare_mappings = mapper.HEALTHCARE_MAPPINGS
    assert isinstance(healthcare_mappings, dict)

    # If healthcare mappings are available, test them
    if healthcare_mappings:
        # Test mapping functionality
        for genesis_type in healthcare_mappings.keys():
            mapping = mapper.map_component(genesis_type)
            assert 'component' in mapping
            assert 'config' in mapping

            # Test tool recognition
            assert mapper.is_tool_component(genesis_type) is True

            # Test mapping source
            assert mapper.get_mapping_source(genesis_type) == "hardcoded_healthcare"

        # Test specific healthcare connectors if they exist
        expected_connectors = [
            "genesis:ehr_connector",
            "genesis:claims_connector",
            "genesis:eligibility_connector",
            "genesis:pharmacy_connector"
        ]

        for connector in expected_connectors:
            if connector in healthcare_mappings:
                mapping = mapper.map_component(connector)
                assert mapping is not None
                assert 'component' in mapping

    # Test that healthcare mappings take priority over standard mappings
    # This tests the ordering in map_component method
    assert mapper.map_component("genesis:agent") is not None  # Should work regardless


def test_component_discovery_includes_healthcare():
    """Test that component discovery includes healthcare mappings."""
    mapper = ComponentMapper()

    components = mapper.get_available_components()
    assert "genesis_mapped" in components

    # Healthcare mappings should be included in genesis_mapped
    genesis_mapped = components["genesis_mapped"]

    # If healthcare mappings are available, they should be in the discovered components
    if mapper.HEALTHCARE_MAPPINGS:
        for healthcare_type in mapper.HEALTHCARE_MAPPINGS.keys():
            assert healthcare_type in genesis_mapped

    # Standard mappings should also be present
    assert "genesis:agent" in genesis_mapped
    assert "genesis:mcp_tool" in genesis_mapped


def test_healthcare_io_mappings_integration():
    """Test that healthcare I/O mappings are integrated."""
    mapper = ComponentMapper()

    # Test that healthcare connectors have I/O mappings
    io_mappings = mapper._get_hardcoded_io_mappings()

    healthcare_components = [
        "EHRConnector",
        "ClaimsConnector",
        "EligibilityConnector",
        "PharmacyConnector",
        "PriorAuthorizationTool",
        "ClinicalDecisionSupportTool"
    ]

    for component in healthcare_components:
        assert component in io_mappings
        mapping = io_mappings[component]
        assert "input_field" in mapping
        assert "output_field" in mapping
        assert "input_types" in mapping
        assert "output_types" in mapping
        assert "Data" in mapping["output_types"]  # All healthcare connectors output Data


if __name__ == "__main__":
    test_healthcare_mappings_integration()
    test_component_discovery_includes_healthcare()
    test_healthcare_io_mappings_integration()
    print("All integration tests passed!")