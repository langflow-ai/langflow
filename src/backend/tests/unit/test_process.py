import pytest
from langflow.processing.process import process_tweaks
from langflow.services.deps import get_session_service


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


@pytest.mark.asyncio
async def test_load_langchain_object_with_cached_session(basic_graph_data):
    # Provide a non-existent session_id
    session_service = get_session_service()
    session_id1 = "non-existent-session-id"
    graph1, artifacts1 = await session_service.load_session(session_id1, basic_graph_data)
    # Use the new session_id to get the langchain_object again
    graph2, artifacts2 = await session_service.load_session(session_id1, basic_graph_data)

    assert graph1 == graph2
    assert artifacts1 == artifacts2


# TODO: Update basic graph data
# @pytest.mark.asyncio
# async def test_load_langchain_object_with_no_cached_session(client, basic_graph_data):
#     # Provide a non-existent session_id
#     session_service = get_session_service()
#     session_id1 = "non-existent-session-id"
#     session_id = session_service.build_key(session_id1, basic_graph_data)
#     graph1, artifacts1 = await session_service.load_session(session_id, data_graph=basic_graph_data, flow_id="flow_id")
#     # Clear the cache
#     await session_service.clear_session(session_id)
#     # Use the new session_id to get the graph again
#     graph2, artifacts2 = await session_service.load_session(session_id, data_graph=basic_graph_data, flow_id="flow_id")

#     # Since the cache was cleared, objects should be different
#     assert id(graph1) != id(graph2)


# @pytest.mark.asyncio
# async def test_load_langchain_object_without_session_id(client, basic_graph_data):
#     # Provide a non-existent session_id
#     session_service = get_session_service()
#     session_id1 = None
#     graph1, artifacts1 = await session_service.load_session(session_id1, data_graph=basic_graph_data, flow_id="flow_id")
#     # Use the new session_id to get the langchain_object again
#     graph2, artifacts2 = await session_service.load_session(session_id1, data_graph=basic_graph_data, flow_id="flow_id")

#     assert graph1 == graph2
