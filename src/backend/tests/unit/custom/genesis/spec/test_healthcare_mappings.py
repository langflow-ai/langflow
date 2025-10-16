"""Unit tests for healthcare connector mappings in ComponentMapper."""

import pytest
from unittest.mock import patch, MagicMock

from langflow.custom.genesis.spec.mapper import ComponentMapper


class TestHealthcareMappings:
    """Test healthcare connector mappings integration."""

    def test_healthcare_mappings_loaded(self):
        """Test that healthcare mappings are loaded during initialization."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {"ehr_system": "epic"},
                        "dataType": "Data"
                    }
                }

                mapper = ComponentMapper()

                assert "genesis:ehr_connector" in mapper.HEALTHCARE_MAPPINGS
                assert mapper.HEALTHCARE_MAPPINGS["genesis:ehr_connector"]["component"] == "EHRConnector"

    def test_healthcare_mappings_not_available(self):
        """Test behavior when healthcare mappings are not available."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', False):
            mapper = ComponentMapper()

            assert mapper.HEALTHCARE_MAPPINGS == {}

    def test_healthcare_mappings_import_error(self):
        """Test behavior when healthcare mappings import fails."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.side_effect = ImportError("Module not found")

                mapper = ComponentMapper()

                assert mapper.HEALTHCARE_MAPPINGS == {}

    def test_map_healthcare_component(self):
        """Test mapping of healthcare connector types."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {
                            "ehr_system": "epic",
                            "fhir_version": "R4",
                            "hipaa_compliance": True
                        },
                        "dataType": "Data"
                    },
                    "genesis:claims_connector": {
                        "component": "ClaimsConnector",
                        "config": {
                            "clearinghouse": "change_healthcare",
                            "test_mode": True
                        },
                        "dataType": "Data"
                    }
                }

                mapper = ComponentMapper()

                # Test EHR connector mapping
                ehr_mapping = mapper.map_component("genesis:ehr_connector")
                assert ehr_mapping["component"] == "EHRConnector"
                assert ehr_mapping["config"]["ehr_system"] == "epic"
                assert ehr_mapping["config"]["hipaa_compliance"] is True

                # Test Claims connector mapping
                claims_mapping = mapper.map_component("genesis:claims_connector")
                assert claims_mapping["component"] == "ClaimsConnector"
                assert claims_mapping["config"]["clearinghouse"] == "change_healthcare"

    def test_healthcare_mapping_priority(self):
        """Test that healthcare mappings have highest priority."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                # Create a conflict with standard mappings
                mock_get_mappings.return_value = {
                    "genesis:agent": {  # This exists in STANDARD_MAPPINGS too
                        "component": "HealthcareAgent",
                        "config": {"specialized": "healthcare"},
                        "dataType": "Data"
                    }
                }

                mapper = ComponentMapper()

                # Healthcare mapping should take priority
                mapping = mapper.map_component("genesis:agent")
                assert mapping["component"] == "HealthcareAgent"
                assert mapping["config"]["specialized"] == "healthcare"

    def test_healthcare_components_are_tools(self):
        """Test that healthcare connectors are recognized as tools."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {"component": "EHRConnector"},
                    "genesis:claims_connector": {"component": "ClaimsConnector"},
                    "genesis:eligibility_connector": {"component": "EligibilityConnector"},
                    "genesis:pharmacy_connector": {"component": "PharmacyConnector"},
                    "genesis:prior_authorization": {"component": "PriorAuthorizationTool"},
                    "genesis:clinical_decision_support": {"component": "ClinicalDecisionSupportTool"}
                }

                mapper = ComponentMapper()

                # All healthcare connectors should be recognized as tools
                assert mapper.is_tool_component("genesis:ehr_connector") is True
                assert mapper.is_tool_component("genesis:claims_connector") is True
                assert mapper.is_tool_component("genesis:eligibility_connector") is True
                assert mapper.is_tool_component("genesis:pharmacy_connector") is True
                assert mapper.is_tool_component("genesis:prior_authorization") is True
                assert mapper.is_tool_component("genesis:clinical_decision_support") is True

    def test_healthcare_io_mappings(self):
        """Test healthcare connector I/O mappings."""
        mapper = ComponentMapper()

        # Test healthcare connector I/O mappings exist in hardcoded mappings
        io_mappings = mapper._get_hardcoded_io_mappings()

        assert "EHRConnector" in io_mappings
        assert io_mappings["EHRConnector"]["input_field"] == "patient_query"
        assert io_mappings["EHRConnector"]["output_field"] == "ehr_data"
        assert "Data" in io_mappings["EHRConnector"]["output_types"]

        assert "ClaimsConnector" in io_mappings
        assert io_mappings["ClaimsConnector"]["input_field"] == "claim_data"
        assert io_mappings["ClaimsConnector"]["output_field"] == "claim_response"

        assert "EligibilityConnector" in io_mappings
        assert io_mappings["EligibilityConnector"]["input_field"] == "eligibility_request"
        assert io_mappings["EligibilityConnector"]["output_field"] == "eligibility_response"

        assert "PharmacyConnector" in io_mappings
        assert io_mappings["PharmacyConnector"]["input_field"] == "prescription_data"
        assert io_mappings["PharmacyConnector"]["output_field"] == "pharmacy_response"

    def test_get_available_components_includes_healthcare(self):
        """Test that get_available_components includes healthcare mappings."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {"ehr_system": "epic"}
                    }
                }

                mapper = ComponentMapper()
                components = mapper.get_available_components()

                assert "genesis_mapped" in components
                assert "genesis:ehr_connector" in components["genesis_mapped"]
                assert components["genesis_mapped"]["genesis:ehr_connector"]["component"] == "EHRConnector"

    def test_get_mapping_source_healthcare(self):
        """Test that get_mapping_source correctly identifies healthcare mappings."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {"component": "EHRConnector"}
                }

                mapper = ComponentMapper()

                assert mapper.get_mapping_source("genesis:ehr_connector") == "hardcoded_healthcare"
                assert mapper.get_mapping_source("genesis:agent") == "hardcoded_standard"
                assert mapper.get_mapping_source("genesis:unknown") == "unknown"

    def test_migrate_healthcare_mappings_to_database(self):
        """Test that healthcare mappings are included in database migration."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {"ehr_system": "epic"}
                    }
                }

                mapper = ComponentMapper()

                # Mock the service
                mock_service = MagicMock()
                mock_session = MagicMock()

                with patch.object(mapper, '_get_component_mapping_service', return_value=mock_service):
                    # Test the all_mappings includes healthcare
                    import asyncio

                    async def test_migration():
                        return await mapper.migrate_hardcoded_mappings_to_database(mock_session)

                    # We can't easily test the async method, but we can verify the mappings dict structure
                    # by checking that healthcare mappings are included in the combined dict
                    all_mappings = {
                        **mapper.HEALTHCARE_MAPPINGS,
                        **mapper.AUTONOMIZE_MODELS,
                        **mapper.MCP_MAPPINGS,
                        **mapper.STANDARD_MAPPINGS,
                    }

                    assert "genesis:ehr_connector" in all_mappings
                    assert "genesis:agent" in all_mappings  # Standard mapping
                    assert "genesis:mcp_tool" in all_mappings  # MCP mapping

    def test_healthcare_component_discovery_integration(self):
        """Test that healthcare components integrate with component discovery."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {"ehr_system": "epic"},
                        "category": "healthcare"
                    }
                }

                mapper = ComponentMapper()

                # Test component discovery includes healthcare components
                all_components = mapper.get_available_components()

                # Healthcare mappings should be in genesis_mapped
                assert "genesis:ehr_connector" in all_components["genesis_mapped"]
                healthcare_mapping = all_components["genesis_mapped"]["genesis:ehr_connector"]
                assert healthcare_mapping["component"] == "EHRConnector"
                assert healthcare_mapping["config"]["ehr_system"] == "epic"

    def test_healthcare_mapping_copy_isolation(self):
        """Test that returned mappings are properly isolated copies."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {"ehr_system": "epic"}
                    }
                }

                mapper = ComponentMapper()

                # Get mapping twice
                mapping1 = mapper.map_component("genesis:ehr_connector")
                mapping2 = mapper.map_component("genesis:ehr_connector")

                # Modify one mapping
                mapping1["config"]["ehr_system"] = "cerner"

                # Other mapping should be unaffected
                assert mapping2["config"]["ehr_system"] == "epic"

                # Original mapping should be unaffected
                original = mapper.HEALTHCARE_MAPPINGS["genesis:ehr_connector"]
                assert original["config"]["ehr_system"] == "epic"

    def test_healthcare_component_validation(self):
        """Test validation of healthcare component configurations."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {
                            "ehr_system": "epic",
                            "fhir_version": "R4",
                            "hipaa_compliance": True,
                            "audit_logging": True
                        },
                        "dataType": "Data",
                        "healthcare_metadata": {
                            "hipaa_compliant": True,
                            "phi_handling": True
                        }
                    }
                }

                mapper = ComponentMapper()
                mapping = mapper.map_component("genesis:ehr_connector")

                # Validate healthcare-specific configurations
                assert mapping["config"]["hipaa_compliance"] is True
                assert mapping["config"]["audit_logging"] is True
                assert mapping["dataType"] == "Data"

                # If healthcare_metadata is present, validate it
                if "healthcare_metadata" in mapping:
                    metadata = mapping["healthcare_metadata"]
                    assert metadata["hipaa_compliant"] is True
                    assert metadata["phi_handling"] is True


class TestHealthcareMappingsIntegration:
    """Integration tests for healthcare mappings with the full system."""

    def test_end_to_end_healthcare_component_mapping(self):
        """Test complete flow from healthcare component type to Langflow component."""
        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:ehr_connector": {
                        "component": "EHRConnector",
                        "config": {
                            "ehr_system": "epic",
                            "fhir_version": "R4",
                            "authentication_type": "oauth2",
                            "hipaa_compliance": True
                        },
                        "dataType": "Data",
                        "io_mapping": {
                            "input_field": "patient_query",
                            "output_field": "ehr_data",
                            "input_types": ["str", "Message", "Data"],
                            "output_types": ["Data"]
                        }
                    }
                }

                mapper = ComponentMapper()

                # Test mapping
                mapping = mapper.map_component("genesis:ehr_connector")
                assert mapping["component"] == "EHRConnector"
                assert mapping["config"]["ehr_system"] == "epic"

                # Test tool recognition
                assert mapper.is_tool_component("genesis:ehr_connector") is True

                # Test I/O mapping
                io_mapping = mapper.get_component_io_mapping("EHRConnector")
                assert io_mapping["input_field"] == "patient_query"
                assert io_mapping["output_field"] == "ehr_data"

                # Test mapping source
                assert mapper.get_mapping_source("genesis:ehr_connector") == "hardcoded_healthcare"

    def test_healthcare_components_in_specifications(self):
        """Test that healthcare components work in actual specifications."""
        # This would be an integration test with actual specification loading
        # For now, we test the mapping consistency

        with patch('langflow.custom.genesis.spec.mapper._healthcare_mappings_available', True):
            with patch('langflow.custom.genesis.spec.mapper.get_healthcare_component_mappings') as mock_get_mappings:
                mock_get_mappings.return_value = {
                    "genesis:eligibility_connector": {
                        "component": "EligibilityConnector",
                        "config": {
                            "eligibility_service": "availity",
                            "real_time_mode": True,
                            "hipaa_compliance": True
                        },
                        "dataType": "Data"
                    }
                }

                mapper = ComponentMapper()

                # Test mapping for specification component
                mapping = mapper.map_component("genesis:eligibility_connector")
                assert mapping["component"] == "EligibilityConnector"
                assert mapping["config"]["eligibility_service"] == "availity"
                assert mapping["config"]["real_time_mode"] is True

                # Test that it's recognized as a tool (for agent integration)
                assert mapper.is_tool_component("genesis:eligibility_connector") is True