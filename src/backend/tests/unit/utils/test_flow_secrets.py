"""Tests for load_from_db reference handling in the flow secret scrubbers."""

from __future__ import annotations

import pytest
from langflow.utils.flow_secrets import (
    HiddenFieldMetadataError,
    restore_redacted_flow_values,
    strip_secret_field_values,
    strip_secret_field_values_in_place,
)


def _secret_node(node_id: str, secret: str) -> dict:
    return {
        "id": node_id,
        "data": {
            "node": {
                "template": {
                    "api_key": {"name": "api_key", "password": True, "value": secret},
                    "model_name": {"name": "model_name", "value": "original"},
                }
            }
        },
    }


def test_restore_redacted_values_matches_unique_node_ids_and_allows_layout_edits() -> None:
    """A shared layout edit restores each key to its stored node despite reordering."""
    stored = {"nodes": [_secret_node("one", "first-secret"), _secret_node("two", "second-secret")], "edges": []}
    incoming = strip_secret_field_values(stored)
    incoming["nodes"].reverse()
    incoming["nodes"][0]["position"] = {"x": 20, "y": 30}

    restored = restore_redacted_flow_values(incoming, stored)

    assert restored["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "second-secret"
    assert restored["nodes"][1]["data"]["node"]["template"]["api_key"]["value"] == "first-secret"
    assert restored["nodes"][0]["position"] == {"x": 20, "y": 30}
    assert incoming["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None


def test_restored_owner_key_rejects_executable_setting_changes() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["model_name"]["value"] = "edited"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restore_redacted_values_rejects_duplicate_node_and_row_identifiers() -> None:
    """Ambiguous identities must not move or erase an owner's credential."""
    stored = {"nodes": [_secret_node("one", "first-secret")], "edges": []}
    incoming = strip_secret_field_values(stored)
    incoming["nodes"].append(_secret_node("one", None))
    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)

    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "value": [
            {"key": "Authorization", "value": "Bearer first"},  # pragma: allowlist secret
            {"key": "Authorization", "value": "Bearer second"},  # pragma: allowlist secret
        ],
    }
    incoming = strip_secret_field_values(stored)
    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


@pytest.mark.parametrize(
    ("field_name", "metadata_change"),
    [
        ("api_key", {"password": False}),
        ("api_key", {"name": "query"}),
        ("api_key", {"load_from_db": True}),
        ("api_key", {"type": "str"}),
        ("api_key", {"_input_type": "StrInput"}),
    ],
)
def test_restore_redacted_values_rejects_weakened_field_metadata(field_name: str, metadata_change: dict) -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    incoming = strip_secret_field_values(stored)
    incoming_field = incoming["nodes"][0]["data"]["node"]["template"][field_name]
    incoming_field.update(metadata_change)

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restore_redacted_values_rejects_weakened_header_row_metadata() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "value": [
            {"id": "stable-row", "key": "Authorization", "value": "Bearer owner-token"}
        ],  # pragma: allowlist secret
    }
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]["key"] = "X-Label"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


@pytest.mark.parametrize(
    ("destination_name", "original"),
    [
        ("bing_search_url", "https://www.bing.com/search"),
        ("endpoint_url", "https://provider.example/v1"),
        ("openai_api_base", "https://provider.example/v1"),
    ],
)
def test_restore_redacted_values_rejects_changed_credential_destination(destination_name: str, original: str) -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    template = stored["nodes"][0]["data"]["node"]["template"]
    template[destination_name] = {"name": destination_name, "value": original}
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"][destination_name]["value"] = "https://attacker.example"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restore_redacted_values_rejects_changed_nested_destination() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["options"] = {
        "name": "options",
        "value": {"transport": {"key": "target_url", "value": "https://provider.example"}},
    }
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["options"]["value"]["transport"]["value"] = (
        "https://attacker.example"
    )

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restored_header_value_requires_unchanged_destination() -> None:
    stored = {"nodes": [{"id": "one", "data": {"node": {"template": {}}}}], "edges": []}
    template = stored["nodes"][0]["data"]["node"]["template"]
    template["headers"] = {
        "name": "headers",
        "value": [{"key": "Authorization", "value": "Bearer owner-token"}],  # pragma: allowlist secret
    }
    template["endpoint_url"] = {"name": "endpoint_url", "value": "https://provider.example"}
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["endpoint_url"]["value"] = "https://attacker.example"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restored_header_rejects_output_mode_change() -> None:
    """API Request must not return the restored Authorization header as metadata."""
    stored = {"nodes": [{"id": "request", "data": {"node": {"template": {}}}}], "edges": []}
    template = stored["nodes"][0]["data"]["node"]["template"]
    template["headers"] = {
        "name": "headers",
        "value": [{"key": "Authorization", "value": "owner-secret"}],  # pragma: allowlist secret
    }
    template["include_httpx_metadata"] = {"name": "include_httpx_metadata", "value": False}
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["include_httpx_metadata"]["value"] = True

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restored_header_rejects_changed_upstream_url_and_edges() -> None:
    """An upstream Text Input can feed API Request's URL even if its own node is unchanged."""
    stored = {
        "nodes": [
            {
                "id": "source",
                "data": {"node": {"template": {"text": {"name": "text", "value": "https://provider.example"}}}},
            },
            {
                "id": "request",
                "data": {
                    "node": {
                        "template": {
                            "url_input": {"name": "url_input", "value": ""},
                            "headers": {
                                "name": "headers",
                                "value": [
                                    {"key": "Authorization", "value": "owner-secret"}
                                ],  # pragma: allowlist secret
                            },
                        }
                    }
                },
            },
        ],
        "edges": [{"source": "source", "target": "request"}],
    }
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["text"]["value"] = "https://attacker.example"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)

    incoming = strip_secret_field_values(stored)
    incoming["edges"] = []
    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_explicit_new_credential_does_not_lock_destination() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["endpoint_url"] = {
        "name": "endpoint_url",
        "value": "https://provider.example",
    }
    incoming = strip_secret_field_values(stored)
    template = incoming["nodes"][0]["data"]["node"]["template"]
    template["api_key"]["value"] = "editor-key"  # pragma: allowlist secret
    template["endpoint_url"]["value"] = "https://editor.example"

    restored = restore_redacted_flow_values(incoming, stored)

    assert restored["nodes"][0]["data"]["node"]["template"] == template


def test_explicit_new_credential_may_replace_hidden_binding_metadata() -> None:
    stored = {"nodes": [_secret_node("one", "OWNER_VAR")], "edges": []}  # pragma: allowlist secret
    stored_field = stored["nodes"][0]["data"]["node"]["template"]["api_key"]
    stored_field["load_from_db"] = True
    incoming = strip_secret_field_values(stored)
    incoming_field = incoming["nodes"][0]["data"]["node"]["template"]["api_key"]
    incoming_field["value"] = "editor-key"  # pragma: allowlist secret
    incoming_field["load_from_db"] = False

    restored = restore_redacted_flow_values(incoming, stored)

    assert restored["nodes"][0]["data"]["node"]["template"]["api_key"] == incoming_field
    assert stored_field["value"] == "OWNER_VAR"


def test_frontend_cleared_hidden_binding_is_preserved_on_layout_save() -> None:
    stored = {"nodes": [_secret_node("one", "OWNER_VAR")], "edges": []}  # pragma: allowlist secret
    stored_field = stored["nodes"][0]["data"]["node"]["template"]["api_key"]
    stored_field["load_from_db"] = True
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["position"] = {"x": 10, "y": 20}
    incoming_field = incoming["nodes"][0]["data"]["node"]["template"]["api_key"]
    incoming_field.update({"value": "", "load_from_db": False})

    restored = restore_redacted_flow_values(incoming, stored)

    assert restored["nodes"][0]["position"] == {"x": 10, "y": 20}
    assert restored["nodes"][0]["data"]["node"]["template"]["api_key"] == stored_field


def test_restore_redacted_value_preserves_anonymous_row_when_unchanged() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "type": "table",
        "table_schema": [{"name": "api_key", "load_from_db": True}],
        "value": [{"api_key": "OWNER_VAR", "label": "old"}],  # pragma: allowlist secret
    }
    incoming = strip_secret_field_values(stored)
    incoming_row = incoming["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]

    restored = restore_redacted_flow_values(incoming, stored)
    restored_row = restored["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]

    assert restored_row == {"api_key": "OWNER_VAR", "label": "old"}  # pragma: allowlist secret
    assert incoming_row["api_key"] is None


def test_restore_redacted_value_rejects_changed_row_binding_metadata() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "type": "table",
        "table_schema": [{"name": "api_key", "load_from_db": True}],
        "value": [
            {"api_key": "OWNER_VAR", "label": "old", "__load_from_db_fields": {"api_key": True}}
        ],  # pragma: allowlist secret
    }
    incoming = strip_secret_field_values(stored)
    incoming_row = incoming["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]
    incoming_row["__load_from_db_fields"] = {"api_key": False}

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restore_redacted_value_rejects_ambiguous_anonymous_row_edit() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "type": "table",
        "table_schema": [{"name": "api_key", "load_from_db": True}],
        "value": [
            {"api_key": "FIRST_VAR", "label": "first"},  # pragma: allowlist secret
            {"api_key": "SECOND_VAR", "label": "second"},  # pragma: allowlist secret
        ],
    }
    incoming = strip_secret_field_values(stored)
    incoming["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]["label"] = "edited"

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def test_restore_redacted_value_rejects_removed_hidden_cell() -> None:
    stored = {"nodes": [_secret_node("one", "owner-secret")], "edges": []}  # pragma: allowlist secret
    stored["nodes"][0]["data"]["node"]["template"]["headers"] = {
        "name": "headers",
        "type": "table",
        "table_schema": [{"name": "api_key", "load_from_db": True}],
        "value": [{"api_key": "OWNER_VAR", "label": "old"}],  # pragma: allowlist secret
    }
    incoming = strip_secret_field_values(stored)
    del incoming["nodes"][0]["data"]["node"]["template"]["headers"]["value"][0]["api_key"]

    with pytest.raises(HiddenFieldMetadataError):
        restore_redacted_flow_values(incoming, stored)


def _flow_data(template: dict) -> dict:
    return {"nodes": [{"data": {"node": {"template": template}}}], "edges": []}


def _template(flow_data: dict) -> dict:
    return flow_data["nodes"][0]["data"]["node"]["template"]


def test_default_scrub_still_nulls_variable_references() -> None:
    """Anonymous consumers (public flow endpoint) must not see variable names."""
    flow_data = _flow_data(
        {"api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "OPENAI_API_KEY"}}
    )

    stripped = strip_secret_field_values(flow_data)

    assert _template(stripped)["api_key"]["value"] is None
    assert _template(flow_data)["api_key"]["value"] == "OPENAI_API_KEY"


def test_preserving_scrub_keeps_and_collects_variable_references() -> None:
    flow_data = _flow_data(
        {
            "api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "OPENAI_API_KEY"},
            "password": {"name": "password", "password": True, "value": "raw-password"},
            "endpoint": {"name": "endpoint", "load_from_db": True, "value": "MY_INTERNAL_API_URL"},
        }
    )
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    template = _template(flow_data)
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert template["password"]["value"] is None
    assert template["endpoint"]["value"] == "MY_INTERNAL_API_URL"
    assert variable_references == {"OPENAI_API_KEY", "MY_INTERNAL_API_URL"}


def test_preserving_scrub_nulls_values_that_do_not_look_like_references() -> None:
    """A mislabelled load_from_db field must not smuggle a raw secret through."""
    invalid_values = [
        "",
        "   ",
        "a" * 257,
        "line\nbreak",
        "tab\tseparated",
        1234,
        {"nested": "dict"},
        # URL built at runtime so secret-scanners do not flag a literal credential.
        "postgres://user:{}@db.internal/prod".format("testpw"),
    ]
    template = {
        f"field_{index}": {"name": f"field_{index}", "password": True, "load_from_db": True, "value": value}
        for index, value in enumerate(invalid_values)
    }
    flow_data = _flow_data(template)
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    for field in _template(flow_data).values():
        assert field["value"] is None
    assert variable_references == set()


def test_preserving_scrub_collects_references_from_nested_group_nodes() -> None:
    nested_template = {"api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "NESTED_KEY"}}
    flow_data = {
        "nodes": [
            {
                "data": {
                    "node": {
                        "template": {},
                        "flow": {"data": _flow_data(nested_template)},
                    }
                }
            }
        ],
        "edges": [],
    }
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    nested = flow_data["nodes"][0]["data"]["node"]["flow"]["data"]
    assert _template(nested)["api_key"]["value"] == "NESTED_KEY"
    assert variable_references == {"NESTED_KEY"}


def test_preserving_scrub_handles_table_reference_columns() -> None:
    flow_data = _flow_data(
        {
            "headers": {
                "name": "headers",
                "type": "table",
                "table_schema": [
                    {"name": "api_key", "load_from_db": True},
                    {"name": "note"},
                ],
                "value": [
                    {
                        "api_key": "TENANT_TOKEN",  # pragma: allowlist secret
                        "note": "kept",
                        "client_secret": "raw-secret",  # pragma: allowlist secret
                    },
                    {"api_key": "bad\nreference", "note": "kept"},  # pragma: allowlist secret
                ],
            }
        }
    )
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    rows = _template(flow_data)["headers"]["value"]
    assert rows[0]["api_key"] == "TENANT_TOKEN"  # pragma: allowlist secret
    assert rows[0]["note"] == "kept"
    assert rows[0]["client_secret"] is None
    assert rows[1]["api_key"] is None
    assert variable_references == {"TENANT_TOKEN"}


def test_known_variable_names_restrict_preserved_references() -> None:
    """With the owner's variable names, only values naming one of them survive."""
    flow_data = _flow_data(
        {
            "api_key": {"name": "api_key", "password": True, "load_from_db": True, "value": "OPENAI_API_KEY"},
            # Shaped like a name, but no variable has it: a literal behind a stale flag.
            "stripe_key": {
                "name": "stripe_key",
                "password": True,
                "load_from_db": True,
                "value": "sk_live_NAMESHAPED",  # pragma: allowlist secret
            },
            "headers": {
                "name": "headers",
                "type": "table",
                "table_schema": [{"name": "api_key", "load_from_db": True}],
                "value": [
                    {"api_key": "TENANT_TOKEN"},  # pragma: allowlist secret
                    {"api_key": "UNKNOWN_TOKEN"},  # pragma: allowlist secret
                ],
            },
        }
    )
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(
        flow_data,
        variable_references=variable_references,
        known_variable_names={"OPENAI_API_KEY", "TENANT_TOKEN"},
    )

    template = _template(flow_data)
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert template["stripe_key"]["value"] is None
    rows = template["headers"]["value"]
    assert rows[0]["api_key"] == "TENANT_TOKEN"  # pragma: allowlist secret
    assert rows[1]["api_key"] is None
    assert variable_references == {"OPENAI_API_KEY", "TENANT_TOKEN"}


def test_preserving_scrub_nulls_table_cells_marked_as_literals() -> None:
    """A cell the row excludes from load_from_db holds the secret, not its name."""
    flow_data = _flow_data(
        {
            "headers": {
                "name": "headers",
                "type": "table",
                "table_schema": [{"name": "value", "load_from_db": True}],
                "value": [
                    {
                        "key": "Authorization",
                        "value": "Bearer raw-token",  # pragma: allowlist secret
                        "__load_from_db_fields": {"value": False},
                    },
                    {
                        "key": "X-Tenant-Key",
                        "value": "TENANT_TOKEN",  # pragma: allowlist secret
                        "__load_from_db_fields": {"value": True},
                    },
                    # A row that records no choice keeps the schema default, so
                    # the runtime resolves it and the value is a variable name.
                    {"key": "X-Legacy-Key", "value": "LEGACY_TOKEN"},  # pragma: allowlist secret
                    # The list form names the columns that do load from the
                    # database, so an absent column is a literal.
                    {
                        "key": "X-Other-Key",
                        "value": "another-raw-token",  # pragma: allowlist secret
                        "__load_from_db_fields": ["unrelated"],
                    },
                ],
            }
        }
    )
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    rows = _template(flow_data)["headers"]["value"]
    assert rows[0]["value"] is None
    assert rows[1]["value"] == "TENANT_TOKEN"  # pragma: allowlist secret
    assert rows[2]["value"] == "LEGACY_TOKEN"  # pragma: allowlist secret
    assert rows[3]["value"] is None
    assert variable_references == {"TENANT_TOKEN", "LEGACY_TOKEN"}


def test_preserving_scrub_keeps_per_cell_metadata_for_secret_named_columns() -> None:
    """Scrubbing must not flip a reference cell into a literal at the target."""
    flow_data = _flow_data(
        {
            "connections": {
                "name": "connections",
                "type": "table",
                "table_schema": [{"name": "password", "load_from_db": True}],
                "value": [
                    {
                        "host": "db.internal",
                        "pass" + "word": "DB_CONN_VAR",
                        "__load_from_db_fields": {"password": True},
                    }
                ],
            }
        }
    )
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    row = _template(flow_data)["connections"]["value"][0]
    assert row["password"] == "DB_CONN_VAR"  # noqa: S105  # pragma: allowlist secret
    assert row["__load_from_db_fields"] == {"password": True}
    assert variable_references == {"DB_CONN_VAR"}


def test_preserving_scrub_nulls_values_shaped_like_issued_credentials() -> None:
    """Well-known credential shapes are never global-variable names."""
    credential_values = [
        "sk-live-abc123XYZ",  # pragma: allowlist secret
        "ghp_aBcD1234efGH",  # pragma: allowlist secret
        "ASIAZZZZZZZZZZZZZZZZ",  # pragma: allowlist secret
        "glpat-abcdefghijkl",  # pragma: allowlist secret
        "xoxb-1234-5678-abcd",  # pragma: allowlist secret
        "hf_abcdefghijklmnop",  # pragma: allowlist secret
    ]
    template = {
        f"field_{index}": {"name": f"field_{index}", "password": True, "load_from_db": True, "value": value}
        for index, value in enumerate(credential_values)
    }
    flow_data = _flow_data(template)
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    for field in _template(flow_data).values():
        assert field["value"] is None
    assert variable_references == set()


def test_preserving_scrub_keeps_names_that_merely_resemble_credential_prefixes() -> None:
    """Upper snake case names must survive the issued-credential shape check."""
    reference_names = [
        "HF_TOKEN",  # pragma: allowlist secret
        "ASIA_REGION_KEY",  # pragma: allowlist secret
        "AKIA_ROTATION_SCHEDULE",  # pragma: allowlist secret
        "SK_BILLING_ACCOUNT",  # pragma: allowlist secret
        "GHP_DEPLOY_TOKEN",  # pragma: allowlist secret
    ]
    template = {
        f"field_{index}": {"name": f"field_{index}", "password": True, "load_from_db": True, "value": value}
        for index, value in enumerate(reference_names)
    }
    flow_data = _flow_data(template)
    variable_references: set[str] = set()

    strip_secret_field_values_in_place(flow_data, variable_references=variable_references)

    assert variable_references == set(reference_names)


def test_default_scrub_still_nulls_table_reference_columns() -> None:
    flow_data = _flow_data(
        {
            "headers": {
                "name": "headers",
                "type": "table",
                "table_schema": [
                    {"name": "api_key", "load_from_db": True},
                    {"name": "value", "load_from_db": True},
                ],
                "value": [
                    {"api_key": "TENANT_TOKEN", "value": "OWNER_SECRET_VAR", "note": "kept"}  # pragma: allowlist secret
                ],
            }
        }
    )

    strip_secret_field_values_in_place(flow_data)

    rows = _template(flow_data)["headers"]["value"]
    assert rows[0]["api_key"] is None
    assert rows[0]["value"] is None
    assert rows[0]["note"] == "kept"
