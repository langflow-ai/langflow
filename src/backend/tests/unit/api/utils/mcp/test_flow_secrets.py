"""The credential scrub must not fail open on the shape of the secret.

``strip_config_secrets`` decides what to rewrite. Two ways it can hand a credential
back to the caller: recognising a literal as an already-substituted reference, and
generating a name that collides with a different server's, since an existing global
variable is deliberately never overwritten.
"""

from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.utils.mcp.flow_secrets import strip_config_secrets, variable_name_for
from langflow.utils.flow_secrets import mcp_header_scope

AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret
UPPERCASE_HEX_TOKEN = "A3F5C9D2E1B8074F"  # noqa: S105  # pragma: allowlist secret


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

    async def test_should_restore_the_latest_masked_value_on_a_retry(self, monkeypatch):
        """A graph rewrite survives rollback, but the server's reference can change."""
        from langflow.api.utils.mcp import flow_secrets as module
        from langflow.services.auth.mcp_encryption import MCP_CONFIG_VALUE_MASK, encrypt_mcp_config

        staged = []

        async def record_variables(variables, user_id, session):  # noqa: ARG001
            staged.append(dict(variables))
            return set()

        monkeypatch.setattr(module, "_ensure_variables", record_variables)
        config = {"headers": {"Authorization": MCP_CONFIG_VALUE_MASK}}
        value = {"name": "ui_svc", "config": config}
        flow_data = {"nodes": [{"data": {"node": {"template": {"mcp_server": {"value": value}}}}}]}
        masked_targets = []
        carried, variables = module.extract_and_strip_mcp_secrets(flow_data, masked_targets=masked_targets)
        row = self._stored("ui_svc", {"Authorization": "{{TOKEN_ONE}}"})
        session = self._session_returning(row)

        await module.stage_mcp_secrets(carried, variables, row.user_id, session, masked_targets=masked_targets)
        assert value["config"]["headers"]["Authorization"] == "{{TOKEN_ONE}}"

        # Simulate a rollback followed by a concurrent update before the next attempt.
        row.config = encrypt_mcp_config({"headers": {"Authorization": "MCP_TOKEN_TWO"}})
        await module.stage_mcp_secrets(carried, variables, row.user_id, session, masked_targets=masked_targets)

        assert value["config"]["headers"]["Authorization"] == "MCP_TOKEN_TWO"
        alias = variable_name_for("ui_svc", "Authorization")
        row.config = encrypt_mcp_config({"headers": {"Authorization": "Bearer test-latest-credential"}})
        await module.stage_mcp_secrets(carried, variables, row.user_id, session, masked_targets=masked_targets)

        assert value["config"]["headers"]["Authorization"] == alias
        row.config = encrypt_mcp_config({"headers": {"Authorization": ""}})
        await module.stage_mcp_secrets(carried, variables, row.user_id, session, masked_targets=masked_targets)
        assert value["config"]["headers"]["Authorization"] == ""

        row.config = encrypt_mcp_config({"headers": {"Authorization": MCP_CONFIG_VALUE_MASK}})
        with pytest.raises(HTTPException) as exc_info:
            await module.stage_mcp_secrets(carried, variables, row.user_id, session, masked_targets=masked_targets)
        assert exc_info.value.status_code == 422
        assert staged == [{}, {}, {alias: "Bearer test-latest-credential"}, {}]
        assert carried == [("ui_svc", config)]
        assert config["headers"]["Authorization"] == MCP_CONFIG_VALUE_MASK
        assert variables == {variable_name_for("ui_svc", "Authorization"): MCP_CONFIG_VALUE_MASK}


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


class TestTheComponentsOwnHeadersBox:
    """The Headers input beside the server field, which overrides the server's headers.

    It is a real place to put auth, and packaging nulls a secret-named entry in it. The
    value was being dropped with no variable declared to put it back, so the deployed
    flow sent no header and nothing said so.
    """

    @staticmethod
    def _rows(headers: dict) -> list:
        """The other shape the canvas stores this box in, which the component also reads."""
        return [{"key": key, "value": value} for key, value in headers.items()]

    @staticmethod
    def _flow(headers, *, server: dict | None = None) -> dict:
        return {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {"value": server if server is not None else {"name": "ui_svc"}},
                                "headers": {
                                    "name": "headers",
                                    "value": list(headers) if isinstance(headers, list) else dict(headers),
                                },
                            }
                        }
                    }
                }
            ]
        }

    @staticmethod
    def _headers(flow_data: dict) -> dict:
        return flow_data["nodes"][0]["data"]["node"]["template"]["headers"]["value"]

    def test_should_move_a_literal_into_its_own_variable(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = self._flow({"Authorization": "Bearer ui-token", "Accept": "application/json"})

        _, variables = extract_and_strip_mcp_secrets(flow_data)

        expected = self._headers(flow_data)["Authorization"]
        assert expected.startswith(variable_name_for(mcp_header_scope("ui_svc"), "Authorization") + "_")
        assert self._headers(flow_data) == {"Authorization": expected, "Accept": "application/json"}
        assert variables == {expected: "Bearer ui-token"}

    def test_should_strip_a_server_selected_by_name_with_no_config(self):
        """Selecting a registered server stores a name and nothing else, which is the usual shape."""
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = self._flow({"Authorization": "Bearer ui-token"}, server={"name": "ui_svc"})

        _, variables = extract_and_strip_mcp_secrets(flow_data)

        assert variables == {self._headers(flow_data)["Authorization"]: "Bearer ui-token"}

    def test_should_keep_that_variable_name_through_packaging(self):
        """Without this the name is nulled again and the deploy declares nothing."""
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow({"Authorization": "Bearer ui-token"})
        extract_and_strip_mcp_secrets(flow_data)
        expected = self._headers(flow_data)["Authorization"]
        references: set[str] = set()

        strip_secret_field_values_in_place(flow_data, variable_references=references)

        assert self._headers(flow_data) == {"Authorization": expected}
        assert references == {expected}

    @pytest.mark.parametrize("as_rows", [False, True])
    @pytest.mark.parametrize("same_flow", [False, True])
    def test_should_keep_each_components_credential_independent(self, as_rows, same_flow):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place
        from lfx.base.mcp.util import _process_headers

        flows = []
        for index, credential in enumerate(("Bearer first-account", "Bearer second-account")):
            headers = {"Authorization": credential}
            flow_data = self._flow(self._rows(headers) if as_rows else headers)
            flow_data["nodes"][0]["id"] = f"MCPTools-{index if same_flow else 'copied'}"
            flows.append(flow_data)
        if same_flow:
            flows[0]["nodes"].extend(flows.pop()["nodes"])

        variables = {}
        for flow_data in flows:
            _, extracted = extract_and_strip_mcp_secrets(flow_data, flow_id=uuid4())
            variables.update(extracted)

        references = set()
        resolved = []
        for flow_data in flows:
            strip_secret_field_values_in_place(
                flow_data, variable_references=references, known_variable_names=variables
            )
            for node in flow_data["nodes"]:
                headers = node["data"]["node"]["template"]["headers"]["value"]
                resolved.append(_process_headers(headers, variables)["authorization"])
        assert resolved == ["Bearer first-account", "Bearer second-account"]
        assert len(references) == 2

    def test_should_not_rotate_the_original_when_editing_a_copy(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        original = self._flow({"Authorization": "Bearer original"})
        original["nodes"][0]["id"] = "MCPTools-copied"
        _, original_variables = extract_and_strip_mcp_secrets(original, flow_id=uuid4())
        copied = deepcopy(original)
        self._headers(copied)["Authorization"] = "Bearer replacement"

        _, copied_variables = extract_and_strip_mcp_secrets(copied, flow_id=uuid4())

        assert original_variables.keys().isdisjoint(copied_variables)
        assert self._headers(original)["Authorization"] != self._headers(copied)["Authorization"]

    def test_should_keep_references_stable_on_resave(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = self._flow({"Authorization": "Bearer original", "X-Tenant": "tenant-123"})
        extract_and_strip_mcp_secrets(flow_data)
        saved = deepcopy(flow_data)

        _, variables = extract_and_strip_mcp_secrets(flow_data)

        assert variables == {}
        assert flow_data == saved

    def test_should_reuse_variables_for_repeated_literal_saves(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_id = uuid4()
        original = self._flow({"Authorization": "Bearer original"})
        original["nodes"][0]["id"] = "MCPTools-first"
        repeated = deepcopy(original)
        _, original_variables = extract_and_strip_mcp_secrets(original, flow_id=flow_id)

        _, repeated_variables = extract_and_strip_mcp_secrets(repeated, flow_id=flow_id)

        assert repeated == original
        assert repeated_variables == original_variables

    def test_should_scope_identical_nested_node_ids_to_their_parents(self):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = {"nodes": []}
        for index, credential in enumerate(("Bearer first-account", "Bearer second-account")):
            nested = self._flow({"Authorization": credential})
            nested["nodes"][0]["id"] = "MCPTools-nested"
            flow_data["nodes"].append({"id": f"group-{index}", "data": {"node": {"flow": {"data": nested}}}})

        _, variables = extract_and_strip_mcp_secrets(flow_data, flow_id=uuid4())

        assert len(variables) == 2
        assert set(variables.values()) == {"Bearer first-account", "Bearer second-account"}

    @pytest.mark.parametrize("as_rows", [False, True])
    @pytest.mark.parametrize("shared_read", [False, True])
    def test_should_hide_a_custom_header_reference_without_its_variable(self, as_rows, shared_read):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        headers = {"X-Api-Key": "live-key", "Accept": "application/json"}
        flow_data = self._flow(self._rows(headers) if as_rows else headers)
        extract_and_strip_mcp_secrets(flow_data)
        references = None if shared_read else set()

        strip_secret_field_values_in_place(flow_data, variable_references=references, known_variable_names=set())

        expected = {"X-Api-Key": None, "Accept": "application/json"}
        assert self._headers(flow_data) == (self._rows(expected) if as_rows else expected)
        assert not references

    @pytest.mark.parametrize("as_rows", [False, True])
    def test_should_refuse_a_snapshot_missing_a_custom_header_variable(self, as_rows):
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.services.deployment_artifacts.builder import (
            ProjectArtifactError,
            _FlowSnapshot,
            _normalized_flow_data,
        )

        headers = {"X-Api-Key": "live-key"}
        flow_data = self._flow(self._rows(headers) if as_rows else headers)
        _, variables = extract_and_strip_mcp_secrets(flow_data)
        snapshot = _FlowSnapshot(flow_id=uuid4(), name="MCP override", payload={"data": flow_data})

        _, required, *_ = _normalized_flow_data(
            snapshot, strict_secret_safety=True, keep_mcp_config=True, known_variable_names=variables
        )
        assert set(required) == set(variables)
        with pytest.raises(ProjectArtifactError, match="cannot be safely captured"):
            _normalized_flow_data(snapshot, strict_secret_safety=True, keep_mcp_config=True, known_variable_names=set())

    @pytest.mark.parametrize(
        "value",
        [
            "Bearer never-stripped",
            "SOME_NAME_NOBODY_GENERATED",
            variable_name_for(mcp_header_scope("other_server"), "Authorization"),
            variable_name_for(mcp_header_scope("ui_svc"), "Authorization") + "_not-a-uuid",
            variable_name_for(mcp_header_scope("ui_svc"), "Authorization") + "_" + "a" * 33,
        ],
    )
    def test_should_null_anything_it_did_not_generate(self, value):
        """Only the name this server and field produce survives, so a literal cannot pass as one."""
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow({"Authorization": value})

        strip_secret_field_values_in_place(flow_data, variable_references=set())

        assert self._headers(flow_data) == {"Authorization": None}

    def test_should_null_it_for_a_reader_with_no_variable_manifest(self):
        """A public share resolves nothing, so it gets the name as little as the secret."""
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow({"Authorization": variable_name_for(mcp_header_scope("ui_svc"), "Authorization")})

        strip_secret_field_values_in_place(flow_data, variable_references=None)

        assert self._headers(flow_data) == {"Authorization": None}

    def test_should_still_null_a_credential_the_generic_rules_catch(self):
        """Lifting the references out must not switch the ordinary scrub off.

        It catches more than a secret-named key: a credential inside a URL under an
        innocent key, and a secret nested deeper in a value. An earlier version of this
        skipped the generic pass for the whole field and lost both.
        """
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow(
            {
                "Authorization": variable_name_for(mcp_header_scope("ui_svc"), "Authorization"),
                "X-Callback": "https://user:pw@internal.example.com/hook",  # pragma: allowlist secret
                "X-Meta": {"api_key": "sk_live_nested"},  # pragma: allowlist secret
                "Accept": "application/json",
            }
        )
        references: set[str] = set()

        strip_secret_field_values_in_place(flow_data, variable_references=references)

        assert self._headers(flow_data) == {
            "Authorization": variable_name_for(mcp_header_scope("ui_svc"), "Authorization"),
            "X-Callback": None,
            "X-Meta": {"api_key": None},
            "Accept": "application/json",
        }
        assert references == {variable_name_for(mcp_header_scope("ui_svc"), "Authorization")}

    def test_should_null_a_name_the_owner_does_not_have(self):
        """Given the owner's real variable names, the reference has to be one of them."""
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow({"Authorization": variable_name_for(mcp_header_scope("ui_svc"), "Authorization")})

        strip_secret_field_values_in_place(
            flow_data, variable_references=set(), known_variable_names={"SOMETHING_ELSE"}
        )

        assert self._headers(flow_data) == {"Authorization": None}

    def test_should_handle_the_box_stored_as_rows_too(self):
        """``DictInput(is_list=True)`` is stored as a mapping or as key/value rows.

        The component reads both at run time, so handling one and not the other misses
        half the flows: the row form created no variable and the credential was dropped.
        """
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow(self._rows({"Authorization": "Bearer ui-token", "Accept": "application/json"}))

        _, variables = extract_and_strip_mcp_secrets(flow_data)
        expected = self._headers(flow_data)[0]["value"]
        references: set[str] = set()
        strip_secret_field_values_in_place(flow_data, variable_references=references)

        assert variables == {expected: "Bearer ui-token"}
        assert self._headers(flow_data) == [
            {"key": "Authorization", "value": expected},
            {"key": "Accept", "value": "application/json"},
        ]
        assert references == {expected}

    def test_should_null_a_literal_stored_as_rows(self):
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow(self._rows({"Authorization": "Bearer never-stripped"}))

        strip_secret_field_values_in_place(flow_data, variable_references=set())

        assert self._headers(flow_data) == [{"key": "Authorization", "value": None}]

    def test_should_not_share_a_variable_with_the_server_config(self):
        """The box overrides the config, so they cannot point at one credential.

        Sharing a name made the config's value win, so the override the author typed was
        silently discarded and the component authenticated with the value it was meant
        to replace.
        """
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets

        flow_data = self._flow(
            {"Authorization": "Bearer from-the-box"},
            server={"name": "ui_svc", "config": {"url": "https://x/mcp", "headers": {"Authorization": "from-config"}}},
        )

        _, variables = extract_and_strip_mcp_secrets(flow_data)

        assert variables[self._headers(flow_data)["Authorization"]] == "Bearer from-the-box"
        assert variables[variable_name_for("ui_svc", "Authorization")] == "from-config"

    def test_should_leave_an_ordinary_routing_header_alone(self):
        """`X-Tenant: acme` is data, not a credential, and must survive untouched.

        An earlier version treated every header outside NON_SECRET_HEADERS as a secret,
        which is the rule a server *config* follows. Here it swept up routing headers
        and turned a tenant id into a variable somebody then had to provision.
        """
        from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
        from langflow.utils.flow_secrets import strip_secret_field_values_in_place

        flow_data = self._flow({"X-Tenant": "acme", "Authorization": "Bearer ui-token"})

        _, variables = extract_and_strip_mcp_secrets(flow_data)
        strip_secret_field_values_in_place(flow_data, variable_references=set())

        reference = self._headers(flow_data)["Authorization"]
        assert list(variables) == [reference]
        assert reference.startswith(variable_name_for(mcp_header_scope("ui_svc"), "Authorization"))
        assert self._headers(flow_data) == {"X-Tenant": "acme", "Authorization": reference}
