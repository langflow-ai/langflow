from langflow.processing.process import process_tweaks
from langflow.services.deps import get_session_service
from langflow.services.utils import register_all_service_factories


def test_no_tweaks():
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 1},
                                "param2": {"value": 2},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3},
                                "param2": {"value": 4},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {}
    result = process_tweaks(graph_data, tweaks)
    assert result == graph_data


def test_single_tweak():
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 1, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {"node1": {"param1": 5}}
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 5, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    result = process_tweaks(graph_data, tweaks)
    assert result == expected_result


def test_multiple_tweaks():
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 1, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {
        "node1": {"param1": 5, "param2": 6},
        "node2": {"param1": 7},
    }
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 5, "type": "int"},
                                "param2": {"value": 6, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 7, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    result = process_tweaks(graph_data, tweaks)
    assert result == expected_result


# Test twekas that just pass the param and value but no node id.
# This is a new feature that was added to the process_tweaks function
def test_tweak_no_node_id():
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 1, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {"param1": 5}
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 5, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 5, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    result = process_tweaks(graph_data, tweaks)
    assert result == expected_result


def test_tweak_not_in_template():
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 1, "type": "int"},
                                "param2": {"value": 2, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 3, "type": "int"},
                                "param2": {"value": 4, "type": "int"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {"node1": {"param3": 5}}
    result = process_tweaks(graph_data, tweaks)
    assert result == graph_data


async def test_load_langchain_object_with_cached_session(basic_graph_data):
    # Provide a non-existent session_id
    register_all_service_factories()
    session_service = get_session_service()
    session_id1 = "non-existent-session-id"
    graph1, artifacts1 = await session_service.load_session(session_id1, basic_graph_data)
    # Use the new session_id to get the langchain_object again
    graph2, artifacts2 = await session_service.load_session(session_id1, basic_graph_data)

    assert graph1 == graph2
    assert artifacts1 == artifacts2


# TODO: Update basic graph data
# async def test_load_langchain_object_with_no_cached_session(client, basic_graph_data):
#     # Provide a non-existent session_id
#     session_service = get_session_service()
#     session_id1 = "non-existent-session-id"
#     session_id = session_service.build_key(session_id1, basic_graph_data)
#     graph1, artifacts1 = await session_service.load_session(
#         session_id, data_graph=basic_graph_data, flow_id="flow_id"
#     )
#     # Clear the cache
#     await session_service.clear_session(session_id)
#     # Use the new session_id to get the graph again
#     graph2, artifacts2 = await session_service.load_session(
#         session_id, data_graph=basic_graph_data, flow_id="flow_id"
#     )
#
#     # Since the cache was cleared, objects should be different
#     assert id(graph1) != id(graph2)


# async def test_load_langchain_object_without_session_id(client, basic_graph_data):
#     # Provide a non-existent session_id
#     session_service = get_session_service()
#     session_id1 = None
#     graph1, artifacts1 = await session_service.load_session(
#         session_id1, data_graph=basic_graph_data, flow_id="flow_id"
#     )
#     # Use the new session_id to get the langchain_object again
#     graph2, artifacts2 = await session_service.load_session(
#         session_id1, data_graph=basic_graph_data, flow_id="flow_id"
#     )
#
#     assert graph1 == graph2


def test_apply_tweaks_code_override_prevention():
    """Test that code tweaks are prevented and logged as warning."""
    from unittest.mock import patch

    from langflow.processing.process import apply_tweaks

    # Create a simple node with template including code field
    node = {
        "id": "test_node",
        "data": {
            "node": {
                "template": {
                    "code": {"value": "original_code", "type": "code"},
                    "param1": {"value": "original_value", "type": "str"},
                }
            }
        },
    }

    # Try to tweak both code and a normal parameter
    node_tweaks = {"code": "malicious_code_injection", "param1": "new_value"}

    # Capture log output
    with patch("langflow.processing.process.logger") as mock_logger:
        apply_tweaks(node, node_tweaks)

        # Verify warning was logged for code override attempt
        mock_logger.warning.assert_called_once_with("Security: Code field cannot be overridden via tweaks.")

    # Verify code field was NOT modified
    assert node["data"]["node"]["template"]["code"]["value"] == "original_code"

    # Verify other parameter WAS modified
    assert node["data"]["node"]["template"]["param1"]["value"] == "new_value"


def test_apply_tweaks_code_only_prevention():
    """Test that only code tweaks are prevented when trying to override code alone."""
    from unittest.mock import patch

    from langflow.processing.process import apply_tweaks

    # Create a simple node with template including code field
    node = {
        "id": "test_node",
        "data": {
            "node": {
                "template": {
                    "code": {"value": "original_code", "type": "code"},
                }
            }
        },
    }

    # Try to tweak only the code field
    node_tweaks = {"code": "attempted_code_injection"}

    # Capture log output
    with patch("langflow.processing.process.logger") as mock_logger:
        apply_tweaks(node, node_tweaks)

        # Verify warning was logged
        mock_logger.warning.assert_called_once_with("Security: Code field cannot be overridden via tweaks.")

    # Verify code field was NOT modified
    assert node["data"]["node"]["template"]["code"]["value"] == "original_code"
