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
    tweaks = {"node1": {"param1": 5}}
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 5},
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
                                "param1": {"value": 5},
                                "param2": {"value": 6},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "param1": {"value": 7},
                                "param2": {"value": 4},
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
    tweaks = {"node1": {"param3": 5}}
    result = process_tweaks(graph_data, tweaks)
    assert result == graph_data


@pytest.mark.asyncio
async def test_load_langchain_object_with_cached_session(client, basic_graph_data):
    # Provide a non-existent session_id
    session_service = get_session_service()
    session_id1 = "non-existent-session-id"
    graph1, artifacts1 = await session_service.load_session(session_id1, basic_graph_data)
    # Use the new session_id to get the langchain_object again
    graph2, artifacts2 = await session_service.load_session(session_id1, basic_graph_data)

    assert graph1 == graph2
    assert artifacts1 == artifacts2


@pytest.mark.asyncio
async def test_load_langchain_object_with_no_cached_session(client, basic_graph_data):
    # Provide a non-existent session_id
    session_service = get_session_service()
    session_id1 = "non-existent-session-id"
    session_id = session_service.build_key(session_id1, basic_graph_data)
    graph1, artifacts1 = await session_service.load_session(session_id, basic_graph_data)
    # Clear the cache
    session_service.clear_session(session_id)
    # Use the new session_id to get the langchain_object again
    graph2, artifacts2 = await session_service.load_session(session_id, basic_graph_data)

    assert id(graph1) != id(graph2)
    # Since the cache was cleared, objects should be different


@pytest.mark.asyncio
async def test_load_langchain_object_without_session_id(client, basic_graph_data):
    # Provide a non-existent session_id
    session_service = get_session_service()
    session_id1 = None
    graph1, artifacts1 = await session_service.load_session(session_id1, basic_graph_data)
    # Use the new session_id to get the langchain_object again
    graph2, artifacts2 = await session_service.load_session(session_id1, basic_graph_data)

    assert graph1 == graph2
