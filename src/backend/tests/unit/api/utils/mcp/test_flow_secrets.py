"""The credential scrub must not fail open on the shape of the secret.

``strip_config_secrets`` decides what to rewrite. Two ways it can hand a credential
back to the caller: recognising a literal as an already-substituted reference, and
generating a name that collides with a different server's, since an existing global
variable is deliberately never overwritten.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
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


class TestUnstorableCredentialFailsTheWrite:
    """Putting the literal back reported success while writing the secret in clear text.

    Restoring traded a leak for a working flow, but the caller was told the save succeeded
    and never learned the credential had landed in an unencrypted column that travels
    through export, share and version history. A control that silently turns itself off is
    worse than one that fails, so the write is refused instead.
    """

    async def test_should_raise_when_a_variable_cannot_be_created(self, monkeypatch):
        import langflow.api.utils.mcp.flow_secrets as module

        async def failing_ensure(variables, user_id, session):  # noqa: ARG001
            return set(variables)

        monkeypatch.setattr(module, "_ensure_variables", failing_ensure)

        name = variable_name_for("billing", "x-api-key")
        with pytest.raises(HTTPException) as exc_info:
            await module.stage_mcp_secrets([], {name: "sk-secret"}, uuid4(), session=None)

        assert exc_info.value.status_code == 500
        assert "sk-secret" not in str(exc_info.value.detail)

    async def test_should_not_raise_when_every_variable_was_stored(self, monkeypatch):
        import langflow.api.utils.mcp.flow_secrets as module

        async def clean_ensure(variables, user_id, session):  # noqa: ARG001
            return set()

        monkeypatch.setattr(module, "_ensure_variables", clean_ensure)

        name = variable_name_for("billing", "x-api-key")

        await module.stage_mcp_secrets([], {name: "sk-secret"}, uuid4(), session=None)


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


class TestNonSecretHeadersAreLeftAlone:
    """Turning ``accept: application/json`` into a Credential variable is noise.

    The list is an allowlist of headers that are never secrets, not a guess at which
    values look secret: failing open on a heuristic would leak, while failing open on
    these specific names cannot.
    """

    def test_should_not_capture_content_negotiation_headers(self):
        config = {
            "url": "https://a.example/mcp",
            "headers": {"accept": "application/json", "content-type": "application/json"},
        }

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is False
        assert variables == {}
        assert stripped["headers"] == config["headers"]

    def test_should_still_capture_a_secret_next_to_them(self):
        config = {
            "url": "https://a.example/mcp",
            "headers": {"accept": "application/json", "x-api-key": "sk-real-secret"},
        }

        stripped, variables, found = strip_config_secrets(config, "billing")

        assert found is True
        assert stripped["headers"]["accept"] == "application/json"
        assert stripped["headers"]["x-api-key"] != "sk-real-secret"
        assert "sk-real-secret" in variables.values()

    def test_should_match_the_header_name_case_insensitively(self):
        config = {"url": "https://a.example/mcp", "headers": {"Accept": "application/json"}}

        _, variables, found = strip_config_secrets(config, "billing")

        assert found is False
        assert variables == {}

    def test_should_never_treat_an_env_entry_as_non_secret(self):
        """The allowlist is about HTTP headers; an env var named accept is not one."""
        config = {"command": "uvx", "env": {"accept": "something"}}

        _, variables, found = strip_config_secrets(config, "billing")

        assert found is True
        assert "something" in variables.values()


class TestNonMcpFlowsCostNothing:
    """A flow without an MCP server must not reach the database on the write path.

    The scrub runs on every flow write. If it opened a savepoint or issued a query for
    flows that carry no credential it would lengthen the write transaction for everyone,
    which on SQLite is how unrelated writers start seeing "database is locked".
    """

    def test_should_extract_nothing_from_a_flow_without_an_mcp_server(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = {
            "nodes": [
                {"data": {"node": {"template": {"input_value": {"value": "hello"}}}}},
                {"data": {"node": {"template": {"path": {"value": "report.txt"}}}}},
            ]
        }

        carried, variables = extract_and_strip_mcp_secrets(flow_data)

        assert carried == []
        assert variables == {}

    async def test_should_not_touch_the_session_when_there_is_nothing_to_stage(self):
        from langflow.api.utils.mcp.flow_secrets import stage_mcp_secrets

        class ExplodingSession:
            def __getattr__(self, name):
                msg = f"the write path must not use the session, but it called {name!r}"
                raise AssertionError(msg)

        await stage_mcp_secrets([], {}, uuid4(), session=ExplodingSession())


class TestRotationIsScopedToAnInteractiveEdit:
    """An import must not re-point a server every other flow of that user shares.

    ``mcp_server`` rows are keyed on (user_id, name), so rotating one on any flow write
    let a single import silently hand every flow bound to that name whatever credential
    the imported file carried — and the previous value is unrecoverable, because the
    encrypted column is overwritten in place. Rotation only makes sense where the user is
    demonstrably editing a server the flow was already bound to.
    """

    @staticmethod
    def _stored(name, headers):
        from langflow.services.auth.mcp_encryption import encrypt_mcp_config
        from langflow.services.database.models import MCPServer

        return MCPServer(user_id=uuid4(), name=name, config=encrypt_mcp_config({"headers": headers}))

    @staticmethod
    def _session_returning(row):
        class Result:
            def first(self):
                return row

        class Session:
            async def exec(self, _stmt):
                return Result()

            def add(self, _row):
                msg = "must not insert when the row already exists"
                raise AssertionError(msg)

        return Session()

    @staticmethod
    def _headers_of(row):
        from langflow.services.auth.mcp_encryption import decrypt_mcp_config

        return decrypt_mcp_config(row.config or {}).get("headers")

    async def test_should_not_rotate_on_an_import(self, monkeypatch):
        import langflow.api.utils.mcp.flow_secrets as module

        async def clean_ensure(variables, user_id, session):  # noqa: ARG001
            return set()

        monkeypatch.setattr(module, "_ensure_variables", clean_ensure)
        row = self._stored("ui_svc", {"Authorization": "Bearer UI-KEY-1"})
        carried = [("ui_svc", {"headers": {"Authorization": "Bearer UI-KEY-2-FROM-LEGACY-EXPORT"}})]

        await module.stage_mcp_secrets(carried, {}, uuid4(), self._session_returning(row))

        assert self._headers_of(row) == {"Authorization": "Bearer UI-KEY-1"}

    async def test_should_rotate_a_server_the_flow_was_already_bound_to(self, monkeypatch):
        import langflow.api.utils.mcp.flow_secrets as module

        async def clean_ensure(variables, user_id, session):  # noqa: ARG001
            return set()

        monkeypatch.setattr(module, "_ensure_variables", clean_ensure)
        row = self._stored("ui_svc", {"Authorization": "Bearer OLD"})
        carried = [("ui_svc", {"headers": {"Authorization": "Bearer ROTATED"}})]

        await module.stage_mcp_secrets(carried, {}, uuid4(), self._session_returning(row), rotatable_servers={"ui_svc"})

        assert self._headers_of(row) == {"Authorization": "Bearer ROTATED"}

    async def test_should_not_rotate_a_server_the_flow_was_not_bound_to(self, monkeypatch):
        """Saving a freshly imported flow must not adopt its credential either."""
        import langflow.api.utils.mcp.flow_secrets as module

        async def clean_ensure(variables, user_id, session):  # noqa: ARG001
            return set()

        monkeypatch.setattr(module, "_ensure_variables", clean_ensure)
        row = self._stored("ui_svc", {"Authorization": "Bearer UI-KEY-1"})
        carried = [("ui_svc", {"headers": {"Authorization": "Bearer IMPORTED"}})]

        await module.stage_mcp_secrets(
            carried, {}, uuid4(), self._session_returning(row), rotatable_servers={"other_svc"}
        )

        assert self._headers_of(row) == {"Authorization": "Bearer UI-KEY-1"}


class TestServerNamesAFlowIsBoundTo:
    def test_should_collect_every_referenced_server_name(self):
        from langflow.api.utils.mcp.flow_secrets import mcp_server_names

        flow_data = {
            "nodes": [
                {"data": {"node": {"template": {"mcp_server": {"value": {"name": "ui_svc", "config": {}}}}}}},
                {"data": {"node": {"template": {"mcp_server": {"value": {"name": "other", "config": {}}}}}}},
            ]
        }

        assert mcp_server_names(flow_data) == {"ui_svc", "other"}

    def test_should_be_empty_for_a_flow_without_mcp_servers(self):
        from langflow.api.utils.mcp.flow_secrets import mcp_server_names

        assert mcp_server_names({"nodes": [{"data": {"node": {"template": {}}}}]}) == set()
