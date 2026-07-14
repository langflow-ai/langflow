from langflow.services.team_templates import sanitize_flow_data


def _flow(template: dict) -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "type": "genericNode",
                "data": {"node": {"template": template}},
            }
        ],
        "edges": [],
    }


def test_sanitize_flow_data_clears_sensitive_variable_and_hidden_values() -> None:
    original = _flow(
        {
            "api_key": {"value": "sk-secret", "password": True, "show": True, "type": "str"},
            "model": {"value": "MODEL_NAME", "load_from_db": True, "show": True, "type": "str"},
            "internal": {"value": "private", "show": False, "type": "str"},
            "hidden_only": {"value": "private-too", "hidden": True},
            "notes": {
                "value": "Bearer abcdefghijklmnopqrstuvwxyz123456",
                "show": True,
                "type": "str",
            },
            "temperature": {"value": 0.7, "advanced": True, "show": True, "type": "float"},
        }
    )

    sanitized, report = sanitize_flow_data(original)
    template = sanitized["nodes"][0]["data"]["node"]["template"]

    assert template["api_key"]["value"] == ""
    assert template["api_key"]["password"] is True
    assert template["model"]["value"] == ""
    assert template["model"]["load_from_db"] is False
    assert template["internal"]["value"] == ""
    assert template["hidden_only"]["value"] == ""
    assert template["notes"]["value"] == ""
    assert template["temperature"]["value"] == 0.7
    assert original["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "sk-secret"
    assert report.cleared_count == 5


def test_sanitize_flow_data_handles_nested_mcp_files_and_table_variables() -> None:
    original = _flow(
        {
            "mcp_server": {
                "value": {"command": "server", "headers": {"Authorization": "Bearer secret"}},
                "show": True,
                "type": "dict",
            },
            "rows": {
                "value": [{"name": "item", "credential": "MY_SECRET"}],
                "show": True,
                "type": "table",
                "table_schema": [
                    {"name": "name", "load_from_db": False},
                    {"name": "credential", "load_from_db": True},
                ],
            },
            "file_path": {"value": "private-file.txt", "show": True, "type": "file"},
        }
    )

    sanitized, _ = sanitize_flow_data(original)
    template = sanitized["nodes"][0]["data"]["node"]["template"]

    assert template["mcp_server"]["value"] == {"command": "server", "headers": {}}
    assert template["rows"]["value"] == [{"name": "item", "credential": ""}]
    assert template["rows"]["table_schema"][1]["load_from_db"] is False
    assert template["file_path"]["value"] == ""


def test_sanitize_flow_data_preserves_structural_hidden_code() -> None:
    original = _flow({"code": {"value": "def build(): pass", "show": False, "type": "code"}})

    sanitized, report = sanitize_flow_data(original)

    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "def build(): pass"
    assert report.cleared_count == 0
