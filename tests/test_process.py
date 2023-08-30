from langflow.interface.run import build_sorted_vertices_with_caching
from langflow.processing.process import load_langchain_object, process_tweaks


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


def test_load_langchain_object_with_cached_session(client, basic_graph_data):
    # Build the langchain_object once and get the session_id
    langchain_object1, artifacts1, session_id1 = load_langchain_object(
        basic_graph_data, None
    )
    # Use the same session_id to get the langchain_object again
    langchain_object2, artifacts2, session_id2 = load_langchain_object(
        basic_graph_data, session_id1
    )

    assert session_id1 == session_id2
    assert id(langchain_object1) == id(langchain_object2)
    assert artifacts1 == artifacts2


def test_load_langchain_object_with_no_cached_session(client, basic_graph_data):
    # Provide a non-existent session_id
    langchain_object1, artifacts1, session_id1 = load_langchain_object(
        basic_graph_data, "non_existent_session"
    )
    # Clear the cache
    build_sorted_vertices_with_caching.clear_cache()
    # Use the new session_id to get the langchain_object again
    langchain_object2, artifacts2, session_id2 = load_langchain_object(
        basic_graph_data, session_id1
    )

    assert session_id1 == session_id2
    assert id(langchain_object1) != id(
        langchain_object2
    )  # Since the cache was cleared, objects should be different


def test_load_langchain_object_without_session_id(client, basic_graph_data):
    # Build the langchain_object without providing a session_id
    langchain_object1, artifacts1, session_id1 = load_langchain_object(
        basic_graph_data, None
    )
    # Build the langchain_object again without providing a session_id
    langchain_object2, artifacts2, session_id2 = load_langchain_object(
        basic_graph_data, None
    )

    assert session_id1 == session_id2

    assert id(langchain_object1) == id(
        langchain_object2
    )  # Since no session_id was provided, the hash will be based on the graph_data
    assert artifacts1 == artifacts2
