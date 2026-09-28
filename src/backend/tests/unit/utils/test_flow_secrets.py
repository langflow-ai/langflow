"""Tests for load_from_db reference handling in the flow secret scrubbers."""

from __future__ import annotations

from copy import deepcopy

import pytest
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


def test_scrub_preserves_only_valid_connection_references() -> None:
    flow_data = _flow_data(
        {
            "valid": {
                "name": "valid",
                "type": "connection_ref",
                "password": True,
                "value": "google_workspace/work",
            },
            "invalid": {
                "name": "invalid",
                "type": "connection_ref",
                "password": True,
                "value": "not a handle",
            },
        }
    )

    stripped = strip_secret_field_values(flow_data)

    assert _template(stripped)["valid"]["value"] == "google_workspace/work"
    assert _template(stripped)["invalid"]["value"] is None


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
                "table_schema": [{"name": "api_key", "load_from_db": True}],
                "value": [{"api_key": "TENANT_TOKEN", "note": "kept"}],  # pragma: allowlist secret
            }
        }
    )

    strip_secret_field_values_in_place(flow_data)

    rows = _template(flow_data)["headers"]["value"]
    assert rows[0]["api_key"] is None
    assert rows[0]["note"] == "kept"


def test_scrub_does_not_null_empty_or_missing_secret_values() -> None:
    """An already-empty or absent value must not gain a spurious ``value: None``."""
    flow_data = _flow_data(
        {
            "empty_password": {"name": "api_key", "password": True, "value": ""},
            "missing_value": {"name": "client_secret", "password": True},
        }
    )
    original = deepcopy(flow_data)

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["empty_password"]["value"] == ""
    assert "value" not in _template(flow_data)["missing_value"]
    assert flow_data == original


def test_scrub_ignores_url_shaped_credentials_in_component_code_comments() -> None:
    """A ``#`` comment mentioning "password" must not be read as a URL fragment."""
    code = (
        "# Enable global variable mode: single-line with password masking\n"
        "# for the API key input, so users never see the raw secret.\n"
        "class TextInput(Component):\n"
        "    display_name = 'Text Input'\n"
    )
    flow_data = _flow_data({"code": {"name": "code", "type": "code", "value": code}})

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["code"]["value"] == code


def test_scrub_ignores_url_shaped_credentials_in_template_pattern_fields() -> None:
    pattern = "# Company Profile\n\n- **Login:** {loginUrl}#password=reset\n"
    flow_data = _flow_data({"pattern": {"name": "pattern", "value": pattern}})

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["pattern"]["value"] == pattern


def test_scrub_still_detects_credentials_in_real_urls() -> None:
    """The narrower check must still catch userinfo and secret-named query params.

    Includes relative and protocol-relative shapes (no scheme, or no scheme and
    no host) alongside absolute URLs: ``urlsplit`` still parses a query string
    or userinfo out of those, and the default (public/anonymous) scrub path
    must null them exactly like it nulls an absolute URL - see LE-1676.
    """
    flow_data = _flow_data(
        {
            "dsn": {"name": "dsn", "value": "postgres://user:{}@db.internal/prod".format("testpw")},
            "webhook": {"name": "webhook", "value": "https://example.com/hook?api_key=live-secret"},
            "padded": {"name": "padded", "value": " https://u:{}@host/db\n".format("testpw")},
            "schemeless": {"name": "schemeless", "value": "api.example.com/v1?access_token=live-secret"},
            "relative": {"name": "relative", "value": "/api/models?api_key=relative-secret"},
            "network": {"name": "network", "value": "//owner:{}@example.com/x".format("network-secret")},
        }
    )

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["dsn"]["value"] is None
    assert _template(flow_data)["webhook"]["value"] is None
    assert _template(flow_data)["padded"]["value"] is None
    assert _template(flow_data)["schemeless"]["value"] is None
    assert _template(flow_data)["relative"]["value"] is None
    assert _template(flow_data)["network"]["value"] is None


def test_scrub_reduces_mcp_config_to_name_only_by_default_for_export() -> None:
    """Every caller gets name-only unless it opts into ``keep_mcp_config``.

    This includes export/publish callers that pass ``variable_references``: file
    export and store publish must never see the config, even a clean one - see
    ``strip_flow_secrets`` callers in projects_files.py and store/service.py.
    """
    flow_data = _flow_data(
        {
            "mcp_server": {
                "name": "mcp_server",
                "type": "mcp",
                "value": {
                    "name": "billing-mcp",
                    "config": {
                        "url": "https://mcp.example.com",
                        "headers": {"Authorization": "MCP_BILLING_MCP_AUTHORIZATION_ABCD1234"},
                    },
                },
            }
        }
    )

    strip_secret_field_values_in_place(flow_data, variable_references=set())

    assert _template(flow_data)["mcp_server"]["value"] == {"name": "billing-mcp"}


def test_scrub_reduces_mcp_config_to_name_only_with_empty_variable_references() -> None:
    """Passing an empty ``variable_references`` set must not by itself unlock the config."""
    flow_data = _flow_data({"mcp_server": {"name": "mcp_server", "type": "mcp", "value": {"config": {"url": "x"}}}})

    strip_secret_field_values_in_place(flow_data, variable_references=set())

    assert _template(flow_data)["mcp_server"]["value"] is None


def test_scrub_keeps_cleaned_mcp_config_with_keep_mcp_config() -> None:
    """The single opt-in caller keeps a provably clean config, verbatim."""
    flow_data = _flow_data(
        {
            "mcp_server": {
                "name": "mcp_server",
                "type": "mcp",
                "value": {
                    "name": "billing-mcp",
                    "config": {
                        "url": "https://mcp.example.com",
                        "headers": {"Authorization": "MCP_BILLING_MCP_AUTHORIZATION_ABCD1234"},
                    },
                },
            }
        }
    )

    strip_secret_field_values_in_place(flow_data, variable_references=set(), keep_mcp_config=True)

    value = _template(flow_data)["mcp_server"]["value"]
    assert value["name"] == "billing-mcp"
    assert value["config"] == {
        "url": "https://mcp.example.com",
        "headers": {"Authorization": "MCP_BILLING_MCP_AUTHORIZATION_ABCD1234"},
    }


def test_scrub_keeps_mcp_config_even_without_a_name_with_keep_mcp_config() -> None:
    """The config is safe on its own; the caller decides whether a nameless entry is usable."""
    flow_data = _flow_data({"mcp_server": {"name": "mcp_server", "type": "mcp", "value": {"config": {"url": "x"}}}})

    strip_secret_field_values_in_place(flow_data, variable_references=set(), keep_mcp_config=True)

    assert _template(flow_data)["mcp_server"]["value"] == {"config": {"url": "x"}}


def test_scrub_nulls_mcp_value_that_is_not_a_dict() -> None:
    flow_data = _flow_data({"mcp_server": {"name": "mcp_server", "type": "mcp", "value": "not-a-dict"}})

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["mcp_server"]["value"] is None


def test_scrub_nulls_empty_mcp_value() -> None:
    flow_data = _flow_data({"mcp_server": {"name": "mcp_server", "type": "mcp", "value": {}}})

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["mcp_server"]["value"] is None


def _legacy_mcp_flow_data() -> dict:
    return _flow_data(
        {
            "mcp_server": {
                "name": "mcp_server",
                "type": "mcp",
                "value": {
                    "name": "srv",
                    "config": {
                        "url": "https://user:pw@mcp.example.com",
                        "headers": {"Authorization": "Bearer sk-live-123"},
                        "env": {"OPENAI_API_KEY": "sk-abc"},
                    },
                },
            }
        }
    )


def test_scrub_reduces_mcp_value_to_name_without_variable_references() -> None:
    """Public and anonymous reads never receive an MCP config, cleaned or not."""
    flow_data = _legacy_mcp_flow_data()

    strip_secret_field_values_in_place(flow_data)

    assert _template(flow_data)["mcp_server"]["value"] == {"name": "srv"}


def test_scrub_reduces_legacy_mcp_secrets_to_name_only_for_export() -> None:
    """A flow saved before save-time MCP stripping must not export its literals."""
    flow_data = _legacy_mcp_flow_data()

    strip_secret_field_values_in_place(flow_data, variable_references=set())

    assert _template(flow_data)["mcp_server"]["value"] == {"name": "srv"}


def test_scrub_nulls_legacy_mcp_secrets_with_keep_mcp_config() -> None:
    """A flow saved before save-time MCP stripping must fail closed, not export its literals."""
    flow_data = _legacy_mcp_flow_data()

    strip_secret_field_values_in_place(flow_data, variable_references=set(), keep_mcp_config=True)

    value = _template(flow_data)["mcp_server"]["value"]
    assert value["name"] == "srv"
    assert value["config"] is None


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            {"url": "https://x.example.com", "headers": {"Authorization": "Bearer sk-live-123"}}, id="literal-header"
        ),
        pytest.param({"command": "uvx", "args": ["run", "--token", "sk-secret"]}, id="args-token-flag"),
        pytest.param({"command": "uvx", "args": ["run", "--api-key=sk-secret"]}, id="args-api-key-flag"),
        pytest.param({"command": "uvx", "args": ["run", "https://user:pw@mcp.example.com"]}, id="args-credential-url"),
        pytest.param({"command": "uvx", "token": "sk-secret"}, id="top-level-token"),  # pragma: allowlist secret
        pytest.param({"command": "uvx", "auth": {"client_secret": "sk-secret"}}, id="nested-client-secret"),
        pytest.param({"url": "https://user:pw@mcp.example.com"}, id="url-userinfo"),
    ],
)
def test_scrub_nulls_unclean_mcp_config_with_keep_mcp_config(config: dict) -> None:
    """``keep_mcp_config`` must never hand back a config it cannot prove is clean."""
    flow_data = _flow_data(
        {"mcp_server": {"name": "mcp_server", "type": "mcp", "value": {"name": "srv", "config": config}}}
    )

    strip_secret_field_values_in_place(flow_data, variable_references=set(), keep_mcp_config=True)

    value = _template(flow_data)["mcp_server"]["value"]
    assert value == {"name": "srv", "config": None}
