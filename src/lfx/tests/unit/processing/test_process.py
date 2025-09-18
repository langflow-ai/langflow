"""Unit tests for alias-enabled tweak processing functionality."""

import pytest

from lfx.processing.process import process_tweaks


class TestAliasProcessing:
    """Test suite for alias functionality in tweak processing."""

    def test_process_tweaks_with_user_defined_alias(self):
        """Test tweak resolution using user-defined aliases."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "MyCustomLLM",
                                "alias_is_user_defined": True,
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    }
                ]
            }
        }

        tweaks = {"MyCustomLLM": {"temperature": 0.8}}

        result = process_tweaks(graph_data, tweaks)

        # Check that the tweak was applied
        node_template = result["data"]["nodes"][0]["data"]["node"]["template"]
        assert node_template["temperature"]["value"] == 0.8

    def test_process_tweaks_with_auto_generated_alias(self):
        """Test tweak resolution using auto-generated aliases."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "OpenAI#1",
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    }
                ]
            }
        }

        tweaks = {"OpenAI#1": {"temperature": 0.7}}

        result = process_tweaks(graph_data, tweaks)

        # Check that the tweak was applied
        node_template = result["data"]["nodes"][0]["data"]["node"]["template"]
        assert node_template["temperature"]["value"] == 0.7

    def test_process_tweaks_with_display_name_fallback(self):
        """Test tweak resolution falls back to display_name for single components."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": None,
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    }
                ]
            }
        }

        tweaks = {"OpenAI": {"temperature": 0.9}}

        result = process_tweaks(graph_data, tweaks)

        # Check that the tweak was applied
        node_template = result["data"]["nodes"][0]["data"]["node"]["template"]
        assert node_template["temperature"]["value"] == 0.9

    def test_process_tweaks_detects_conflicting_keys(self):
        """Test that conflicting tweaks for the same component raise an informative error."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "specific-node-id",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "OpenAI#1",
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    }
                ]
            }
        }

        tweaks = {"specific-node-id": {"temperature": 0.6}, "OpenAI#1": {"temperature": 0.8}}

        # Should raise informative error about conflicting keys
        with pytest.raises(ValueError, match="Conflicting tweaks found for the same component"):
            process_tweaks(graph_data, tweaks)

    def test_process_tweaks_multiple_components_with_aliases(self):
        """Test tweak resolution with multiple components having different aliases."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "OpenAI#1",
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    },
                    {
                        "id": "node-2",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "MyProductionLLM",
                                "alias_is_user_defined": True,
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    },
                ]
            }
        }

        tweaks = {"OpenAI#1": {"temperature": 0.7}, "MyProductionLLM": {"temperature": 0.3}}

        result = process_tweaks(graph_data, tweaks)

        # Check that both tweaks were applied correctly
        node1_template = result["data"]["nodes"][0]["data"]["node"]["template"]
        node2_template = result["data"]["nodes"][1]["data"]["node"]["template"]
        assert node1_template["temperature"]["value"] == 0.7
        assert node2_template["temperature"]["value"] == 0.3

    def test_process_tweaks_no_alias_conflict_with_display_name(self):
        """Test that display_name fallback doesn't conflict with aliased components."""
        graph_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "node": {
                                "display_name": "OpenAI",
                                "alias": "OpenAI#1",  # Has alias, so display_name won't be mapped
                                "template": {"temperature": {"value": 0.5, "type": "float"}},
                            }
                        },
                    },
                    {
                        "id": "node-2",
                        "data": {
                            "node": {
                                "display_name": "Wikipedia",
                                "alias": None,  # No alias, so display_name will be mapped
                                "template": {"query": {"value": "test", "type": "str"}},
                            }
                        },
                    },
                ]
            }
        }

        tweaks = {
            "OpenAI": {  # This should NOT match node-1 since it has an alias
                "temperature": 0.9
            },
            "Wikipedia": {  # This should match node-2 since it has no alias
                "query": "new query"
            },
        }

        result = process_tweaks(graph_data, tweaks)

        # OpenAI tweak should not be applied (no match)
        node1_template = result["data"]["nodes"][0]["data"]["node"]["template"]
        assert node1_template["temperature"]["value"] == 0.5  # Original value

        # Wikipedia tweak should be applied
        node2_template = result["data"]["nodes"][1]["data"]["node"]["template"]
        assert node2_template["query"]["value"] == "new query"
