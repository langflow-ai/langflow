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


def test_tweak_no_node_id_boolean():
    """Test that boolean tweaks at root level are applied to all matching nodes."""
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "enabled": {"value": True, "type": "bool"},
                                "param1": {"value": "hello", "type": "str"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "enabled": {"value": True, "type": "bool"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {"enabled": False}
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "enabled": {"value": False, "type": "bool"},
                                "param1": {"value": "hello", "type": "str"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "enabled": {"value": False, "type": "bool"},
                            }
                        }
                    },
                },
            ]
        }
    }
    result = process_tweaks(graph_data, tweaks)
    assert result == expected_result


def test_tweak_no_node_id_numeric():
    """Test that numeric tweaks at root level are applied to all matching nodes."""
    graph_data = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "temperature": {"value": 1.0, "type": "float"},
                                "max_tokens": {"value": 100, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "temperature": {"value": 1.0, "type": "float"},
                            }
                        }
                    },
                },
            ]
        }
    }
    tweaks = {"temperature": 0.7, "max_tokens": 256}
    expected_result = {
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "node": {
                            "template": {
                                "temperature": {"value": 0.7, "type": "float"},
                                "max_tokens": {"value": 256, "type": "int"},
                            }
                        }
                    },
                },
                {
                    "id": "node2",
                    "data": {
                        "node": {
                            "template": {
                                "temperature": {"value": 0.7, "type": "float"},
                            }
                        }
                    },
                },
            ]
        }
    }
    result = process_tweaks(graph_data, tweaks)
    assert result == expected_result


def test_tweaks_schema_accepts_bool():
    """Tweaks model must accept boolean root-level values without coercion."""
    from lfx.schema.graph import Tweaks

    tweaks = Tweaks(root={"stream": False, "enabled": True})
    assert tweaks.root["stream"] is False
    assert tweaks.root["enabled"] is True
    # Verify bool is preserved and not coerced to int
    assert isinstance(tweaks.root["stream"], bool)
    assert isinstance(tweaks.root["enabled"], bool)


def test_tweaks_schema_accepts_numerics():
    """Tweaks model must accept int and float root-level values."""
    from lfx.schema.graph import Tweaks

    tweaks = Tweaks(root={"temperature": 0.7, "max_tokens": 256})
    assert tweaks.root["temperature"] == 0.7
    assert tweaks.root["max_tokens"] == 256


def test_tweaks_schema_rejects_invalid():
    """Tweaks model should still reject unsupported value types."""
    import pytest
    from lfx.schema.graph import Tweaks
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Tweaks(root={"param": [1, 2, 3]})


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

        # Verify warning was logged for code override attempt (and names the field)
        mock_logger.warning.assert_called_once_with("Security: refusing to override code field 'code' via tweaks.")

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

        # Verify warning was logged and names the offending field (not a generic "Code field").
        mock_logger.warning.assert_called_once_with("Security: refusing to override code field 'code' via tweaks.")

    # Verify code field was NOT modified
    assert node["data"]["node"]["template"]["code"]["value"] == "original_code"


def test_apply_tweaks_blocks_code_type_field_with_other_name():
    """A code-injection bypass: a field of type 'code' but named something other than 'code'.

    The old guard only blocked the literal field name 'code'. Block by field *type*.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "node": {
                "template": {
                    "custom_source": {"value": "original", "type": "code"},
                    "param1": {"value": "ok", "type": "str"},
                }
            }
        },
    }
    apply_tweaks(node, {"custom_source": "import os; os.system('id')", "param1": "new"})

    # The code-type field must NOT be overridden; the ordinary field is fine.
    assert node["data"]["node"]["template"]["custom_source"]["value"] == "original"
    assert node["data"]["node"]["template"]["param1"]["value"] == "new"


def test_apply_tweaks_blocks_code_execution_component_fields():
    """Tweaks must not override the executable/sandbox inputs of a code-execution component.

    The executable input lives under names like 'python_code' (MultilineInput → type
    'str'), not 'code', so the block keys off the component *type*
    (CODE_EXECUTION_COMPONENT_TYPES) plus the code/sandbox field names
    (CODE_EXECUTION_FIELD_NAMES). 'global_imports' is the import allow-list that
    populates the exec() namespace and must stay blocked too.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "type": "PythonREPLComponent",
            "node": {
                "template": {
                    "python_code": {"value": "print('safe')", "type": "str"},
                    "global_imports": {"value": "math", "type": "str"},
                }
            },
        },
    }
    apply_tweaks(node, {"python_code": "__import__('os').system('id')", "global_imports": "os,subprocess"})

    assert node["data"]["node"]["template"]["python_code"]["value"] == "print('safe')"
    assert node["data"]["node"]["template"]["global_imports"]["value"] == "math"


def test_apply_tweaks_allows_benign_fields_on_code_execution_component():
    """Scoped block: benign fields on a code-execution component remain tweakable.

    Regression for the over-block where every field on a code-execution node was
    dropped — renaming a Python REPL tool (name/description) must still work.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "type": "PythonREPLTool",
            "node": {
                "template": {
                    "name": {"value": "old_name", "type": "str"},
                    "description": {"value": "old desc", "type": "str"},
                    "code": {"value": "print('safe')", "type": "str"},
                }
            },
        },
    }
    apply_tweaks(node, {"name": "new_name", "description": "new desc", "code": "__import__('os').system('id')"})

    # Benign metadata is applied; the executable 'code' field is still blocked.
    assert node["data"]["node"]["template"]["name"]["value"] == "new_name"
    assert node["data"]["node"]["template"]["description"]["value"] == "new desc"
    assert node["data"]["node"]["template"]["code"]["value"] == "print('safe')"


def test_apply_tweaks_blocks_removed_python_code_structured_tool_code():
    """The removed PythonCodeStructuredTool's exec input is 'tool_code' (type 'str').

    Its type is retained in CODE_EXECUTION_COMPONENT_TYPES to keep stored code in
    existing flows un-overridable; the tweak guard must cover 'tool_code' too.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "type": "PythonCodeStructuredTool",
            "node": {"template": {"tool_code": {"value": "stored_code", "type": "str"}}},
        },
    }
    apply_tweaks(node, {"tool_code": "__import__('os').system('id')"})

    assert node["data"]["node"]["template"]["tool_code"]["value"] == "stored_code"


def test_apply_tweaks_blocks_csv_agent_dangerous_code_flag():
    """CSVAgent's LangChain Python-execution opt-in is a sandbox boundary."""
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "type": "CSVAgent",
            "node": {
                "template": {
                    "allow_dangerous_code": {"value": False, "type": "bool"},
                    "input_value": {"value": "summarize", "type": "str"},
                }
            },
        },
    }
    apply_tweaks(node, {"allow_dangerous_code": True, "input_value": "count rows"})

    assert node["data"]["node"]["template"]["allow_dangerous_code"]["value"] is False
    assert node["data"]["node"]["template"]["input_value"]["value"] == "count rows"


def test_apply_tweaks_smart_transform_blocks_instruction_allows_data():
    """Smart Transform's 'filter_instruction' drives an eval()'d lambda → blocked.

    Other inputs (data, sample_size, ...) carry no code and stay tweakable.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "n",
        "data": {
            "type": "Smart Transform",
            "node": {
                "template": {
                    "filter_instruction": {"value": "uppercase the text", "type": "str"},
                    "sample_size": {"value": 10, "type": "int"},
                }
            },
        },
    }
    apply_tweaks(node, {"filter_instruction": "lambda x: __import__('os').system('id')", "sample_size": 25})

    assert node["data"]["node"]["template"]["filter_instruction"]["value"] == "uppercase the text"
    assert node["data"]["node"]["template"]["sample_size"]["value"] == 25


def test_apply_tweaks_mcp_field_type():
    """Test that MCP field types are handled correctly with dict values."""
    from langflow.processing.process import apply_tweaks

    # Create a node with an MCP field type
    node = {
        "id": "test_node",
        "data": {
            "node": {
                "template": {
                    "mcp_server": {
                        "value": {"name": "original_server", "config": {}},
                        "type": "mcp",
                    },
                    "param1": {"value": "original_value", "type": "str"},
                }
            }
        },
    }

    # Tweak the MCP field with a dict value
    node_tweaks = {
        "mcp_server": {"name": "new_server", "config": {"url": "http://example.com"}},
        "param1": "new_value",
    }

    apply_tweaks(node, node_tweaks)

    # Verify MCP field was set directly (not merged)
    assert node["data"]["node"]["template"]["mcp_server"]["value"] == {
        "name": "new_server",
        "config": {"url": "http://example.com"},
    }

    # Verify other parameter was also modified
    assert node["data"]["node"]["template"]["param1"]["value"] == "new_value"


def test_apply_tweaks_mcp_field_with_string_value():
    """Test that MCP field types handle string values correctly."""
    from langflow.processing.process import apply_tweaks

    # Create a node with an MCP field type
    node = {
        "id": "test_node",
        "data": {
            "node": {
                "template": {
                    "mcp_server": {
                        "value": None,
                        "type": "mcp",
                    },
                }
            }
        },
    }

    # Tweak the MCP field with a string value (server name)
    node_tweaks = {"mcp_server": "simple_server_name"}

    apply_tweaks(node, node_tweaks)

    # Verify MCP field was set directly
    assert node["data"]["node"]["template"]["mcp_server"]["value"] == "simple_server_name"


def test_apply_tweaks_field_type_extraction():
    """Test that field type is safely extracted with .get() to avoid KeyError."""
    from langflow.processing.process import apply_tweaks

    # Create a node with a field that has no explicit type
    node = {
        "id": "test_node",
        "data": {
            "node": {
                "template": {
                    "param_no_type": {"value": "original"},
                    "param_with_type": {"value": "original", "type": "str"},
                }
            }
        },
    }

    # Tweak both fields
    node_tweaks = {
        "param_no_type": "new_value_1",
        "param_with_type": "new_value_2",
    }

    # Should not raise KeyError even though param_no_type has no "type" key
    apply_tweaks(node, node_tweaks)

    # Verify both fields were modified
    assert node["data"]["node"]["template"]["param_no_type"]["value"] == "new_value_1"
    assert node["data"]["node"]["template"]["param_with_type"]["value"] == "new_value_2"


def test_apply_tweaks_dict_field_type():
    """Test that dict field types (e.g. DictInput headers) set the value directly.

    Previously, passing a dict tweak for a 'dict' field type would iterate over
    the dict keys and set them as top-level template properties instead of setting
    the field's value. This caused headers passed via tweaks to be ignored.
    """
    from langflow.processing.process import apply_tweaks

    # Create a node with a dict field type (like MCP Tools headers)
    node = {
        "id": "MCPTools-322Z0",
        "data": {
            "node": {
                "template": {
                    "headers": {
                        "value": [
                            {"key": "header1", "value": "default1"},
                            {"key": "header2", "value": "default2"},
                        ],
                        "type": "dict",
                    },
                }
            }
        },
    }

    # Tweak headers with a plain dict (as sent via API tweaks)
    node_tweaks = {
        "headers": {"header1": "override1", "header2": "override2", "header3": "new3"},
    }

    apply_tweaks(node, node_tweaks)

    # Verify the dict was set directly as the value, not spread as template properties
    assert node["data"]["node"]["template"]["headers"]["value"] == {
        "header1": "override1",
        "header2": "override2",
        "header3": "new3",
    }
    # Ensure the tweak keys were NOT set as top-level template field properties
    assert "header1" not in node["data"]["node"]["template"]["headers"]
    assert "header2" not in node["data"]["node"]["template"]["headers"]
    assert "header3" not in node["data"]["node"]["template"]["headers"]


def test_apply_tweaks_dict_field_overwrites_list_default():
    """Test that a dict tweak fully replaces a list-format default value on a dict field."""
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "node1",
        "data": {
            "node": {
                "template": {
                    "headers": {
                        "value": [{"key": "old", "value": "old_val"}],
                        "type": "dict",
                    },
                }
            }
        },
    }

    apply_tweaks(node, {"headers": {"new_key": "new_val"}})

    # The dict tweak should fully replace the old list value
    assert node["data"]["node"]["template"]["headers"]["value"] == {"new_key": "new_val"}


def test_apply_tweaks_dict_field_value_wrapped_list():
    """Test that dict field tweaks wrapped in {"value": [...]} are unwrapped correctly.

    When users pass tweaks in the template-format style (e.g. from UI exports),
    the list of key-value pairs is wrapped in a "value" key. The tweak should
    unwrap this and set the inner list as the field's value.
    """
    from langflow.processing.process import apply_tweaks

    node = {
        "id": "MCPTools-svrRq",
        "data": {
            "node": {
                "template": {
                    "headers": {
                        "value": [],
                        "type": "dict",
                    },
                }
            }
        },
    }

    # Tweak using the template-format wrapper: {"value": [list of key-value pairs]}
    node_tweaks = {
        "headers": {
            "value": [
                {"key": "header1", "value": "gabriel1"},
                {"key": "header2", "value": "gabriel2"},
            ]
        },
    }

    apply_tweaks(node, node_tweaks)

    # The inner list should be unwrapped and set as the field's value
    assert node["data"]["node"]["template"]["headers"]["value"] == [
        {"key": "header1", "value": "gabriel1"},
        {"key": "header2", "value": "gabriel2"},
    ]
