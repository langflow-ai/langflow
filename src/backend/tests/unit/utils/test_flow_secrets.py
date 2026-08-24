"""Tests for load_from_db reference handling in the flow secret scrubbers."""

from __future__ import annotations

from langflow.utils.flow_secrets import strip_secret_field_values, strip_secret_field_values_in_place


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
                "table_schema": [{"name": "api_key", "load_from_db": True}],
                "value": [{"api_key": "TENANT_TOKEN", "note": "kept"}],  # pragma: allowlist secret
            }
        }
    )

    strip_secret_field_values_in_place(flow_data)

    rows = _template(flow_data)["headers"]["value"]
    assert rows[0]["api_key"] is None
    assert rows[0]["note"] == "kept"
