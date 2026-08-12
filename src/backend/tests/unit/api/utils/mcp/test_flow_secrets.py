"""The credential scrub must not fail open on the shape of the secret.

``strip_config_secrets`` decides what to rewrite. Two ways it can hand a credential
back to the caller: recognising a literal as an already-substituted reference, and
generating a name that collides with a different server's, since an existing global
variable is deliberately never overwritten.
"""

from langflow.api.utils.mcp.flow_secrets import strip_config_secrets, variable_name_for

AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
UPPERCASE_HEX_TOKEN = "A3F5C9D2E1B8074F"  # noqa: S105


class TestSecretsThatLookLikeIdentifiers:
    """A value is not a reference just because it is spelled in capitals."""

    def test_should_rewrite_an_aws_access_key_id(self):
        config = {"url": "https://a.example/mcp", "headers": {"x-api-key": AWS_ACCESS_KEY_ID}}

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is True
        assert stripped["headers"]["x-api-key"] != AWS_ACCESS_KEY_ID
        assert AWS_ACCESS_KEY_ID in variables.values()

    def test_should_rewrite_an_uppercase_hex_token(self):
        config = {"url": "https://a.example/mcp", "headers": {"authorization": UPPERCASE_HEX_TOKEN}}

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is True
        assert stripped["headers"]["authorization"] != UPPERCASE_HEX_TOKEN
        assert UPPERCASE_HEX_TOKEN in variables.values()

    def test_should_leave_a_name_this_module_generated(self):
        """A re-save must not wrap its own reference a second time."""
        reference = variable_name_for("billing", "x-api-key")
        config = {"url": "https://a.example/mcp", "headers": {"x-api-key": reference}}

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is False
        assert stripped["headers"]["x-api-key"] == reference
        assert variables == {}

    def test_should_leave_an_explicit_placeholder(self):
        config = {"url": "https://a.example/mcp", "headers": {"x-api-key": "{{MY_KEY}}"}}

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is False
        assert stripped["headers"]["x-api-key"] == "{{MY_KEY}}"
        assert variables == {}


class TestVariableNameIsInjective:
    """Distinct servers must never be pointed at one another's credential.

    ``_ensure_variables`` leaves an existing variable alone, so two servers that
    generate the same name means the second silently authenticates with the first
    server's key — against a different target.
    """

    def test_should_not_collide_across_separator_spellings(self):
        names = {
            variable_name_for("billing-mcp", "x-api-key"),
            variable_name_for("billing_mcp", "x-api-key"),
            variable_name_for("billing.mcp", "x-api-key"),
        }

        assert len(names) == 3, f"names collapsed to {names}"

    def test_should_not_collide_across_header_spellings(self):
        names = {
            variable_name_for("billing", "x-api-key"),
            variable_name_for("billing", "x_api_key"),
            variable_name_for("billing", "X-API-KEY"),
        }

        assert len(names) == 3, f"names collapsed to {names}"

    def test_should_be_stable_for_the_same_pair(self):
        """A re-save has to land on the variable the previous save created."""
        first = variable_name_for("billing-mcp", "x-api-key")
        second = variable_name_for("billing-mcp", "x-api-key")

        assert first == second

    def test_should_stay_readable_and_prefixed(self):
        name = variable_name_for("billing-mcp", "x-api-key")

        assert name.startswith("MCP_")
        assert "BILLING_MCP" in name


class TestCredentialIsNeverLost:
    """Stripping a secret the runtime cannot resolve trades a leak for a broken flow."""

    def test_should_restore_the_literal_when_its_variable_failed(self):
        from langflow.api.utils.mcp.flow_secrets import restore_unresolvable_references

        secret = "sk-only-copy-of-this"  # noqa: S105
        name = variable_name_for("billing", "x-api-key")
        flow_data = {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {"value": {"name": "billing", "config": {"headers": {"x-api-key": name}}}}
                            }
                        }
                    }
                }
            ]
        }

        restore_unresolvable_references(flow_data, {name: secret}, {name})

        config = flow_data["nodes"][0]["data"]["node"]["template"]["mcp_server"]["value"]["config"]
        assert config["headers"]["x-api-key"] == secret

    def test_should_leave_resolvable_references_alone(self):
        from langflow.api.utils.mcp.flow_secrets import restore_unresolvable_references

        name = variable_name_for("billing", "x-api-key")
        flow_data = {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {"value": {"name": "billing", "config": {"headers": {"x-api-key": name}}}}
                            }
                        }
                    }
                }
            ]
        }

        restore_unresolvable_references(flow_data, {name: "sk-secret"}, set())

        config = flow_data["nodes"][0]["data"]["node"]["template"]["mcp_server"]["value"]["config"]
        assert config["headers"]["x-api-key"] == name


def test_should_not_commit_inside_the_helper():
    """The batch write path documents itself as all-or-nothing; a commit here breaks it."""
    from pathlib import Path

    from langflow.api.utils.mcp import flow_secrets as flow_secrets_module

    module = Path(flow_secrets_module.__file__)
    source = module.read_text(encoding="utf-8")

    assert "session.commit()" not in source


class TestStagingSurvivesARetry:
    """A rollback discards the staged rows; the in-place rewrite of the flow survives it.

    Re-extracting on the second attempt would find only the reference the first attempt
    wrote, stage nothing, and let the flow commit pointing at a variable that was never
    created. Extraction therefore happens once and staging happens per attempt.
    """

    def test_should_find_nothing_on_a_second_extraction(self):
        """Documents why re-extracting per attempt cannot work."""
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "value": {
                                        "name": "billing",
                                        "config": {"headers": {"x-api-key": "sk-real-secret"}},
                                    }
                                }
                            }
                        }
                    }
                }
            ]
        }

        first_carried, first_variables = extract_and_strip_mcp_secrets(flow_data)
        second_carried, second_variables = extract_and_strip_mcp_secrets(flow_data)

        assert first_carried
        assert first_variables
        assert second_carried == [], "a retry would stage nothing"
        assert second_variables == {}, "a retry would stage nothing"

    def test_should_expose_staging_separately_from_extraction(self):
        from langflow.api.utils.mcp import flow_secrets

        assert hasattr(flow_secrets, "stage_mcp_secrets")
        assert hasattr(flow_secrets, "extract_and_strip_mcp_secrets")
