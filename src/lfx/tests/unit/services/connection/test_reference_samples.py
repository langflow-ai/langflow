"""INT-13: the headless reference samples run, and keep their security invariants.

``docs/docs/Lfx/lfx-connections.mdx`` embeds these files verbatim. Operators copy
them into production, so the tests pin the parts that make them safe as well as
the parts that make them work: the headless-only deny floor, the refusal of
long-lived secrets, typed expiry and scope failures, and fail-closed registration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
from lfx.integrations import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionRef,
    ConnectionResolutionRequest,
    ConnectionUnresolvedError,
    ScopeMissingError,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService
from lfx.services.manager import ServiceManager
from lfx.services.variable.service import VariableService

from tests.unit.services.connection.sample_loader import load_connection_sample, requires_samples

pytestmark = requires_samples

HANDLE = "google/work"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


@pytest.fixture
def env_sample():
    return load_connection_sample("env_resolver_host")


@pytest.fixture
def secret_sample():
    return load_connection_sample("secret_manager_resolver")


@pytest.fixture
def variable_service(monkeypatch: pytest.MonkeyPatch) -> VariableService:
    """Give the env resolver a service that reads request scope, then the environment."""
    service = VariableService()
    monkeypatch.setattr("lfx.services.deps.get_variable_service", lambda: service)
    return service


def _request(*, principal: ExecutionPrincipal | None = None, scopes: frozenset[str] = frozenset()):
    return ConnectionResolutionRequest(
        ref=ConnectionRef.parse(HANDLE),
        principal=principal or ExecutionPrincipal(kind="headless_operator"),
        required_scopes=scopes,
    )


# --------------------------------------------------------------------------- #
# env_resolver_host.py
# --------------------------------------------------------------------------- #


def test_env_key_helper_matches_the_documented_derivation(env_sample) -> None:
    assert env_sample.env_key_for(HANDLE) == "LF_CONNECTION__GOOGLE__WORK"
    # Provider punctuation is hex-escaped so a.b, a-b and a_b cannot collide.
    assert env_sample.env_key_for("test.provider/work") == "LF_CONNECTION__TEST_2EPROVIDER__WORK"


async def test_env_sample_resolves_a_bare_token_from_the_environment(
    env_sample,
    variable_service: VariableService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = variable_service
    monkeypatch.setenv("LF_CONNECTION__GOOGLE__WORK", "ambient-token")

    credential = await env_sample.resolve_from_process_environment(HANDLE)

    assert credential.access_token.get_secret_value() == "ambient-token"
    assert credential.owner_kind == "env"
    # A bare token asserts nothing, so no scope claim is verified.
    assert credential.scopes_verified is False
    assert "ambient-token" not in repr(credential)


async def test_env_sample_request_scope_beats_the_environment(
    env_sample,
    variable_service: VariableService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = variable_service
    key = env_sample.env_key_for(HANDLE)
    monkeypatch.setenv(key, "ambient-token")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    value = env_sample.credential_json(
        "request-token",  # pragma: allowlist secret
        expires_at=expires_at,
        scopes=[DRIVE_SCOPE],
        account_id="person@example.com",
    )

    credential = await env_sample.resolve_with_request_scope(
        HANDLE,
        {key: value},
        required_scopes=[DRIVE_SCOPE],
    )

    assert credential.access_token.get_secret_value() == "request-token"
    assert credential.scopes_verified is True
    assert credential.account is not None
    assert credential.account.id == "person@example.com"


def test_env_sample_credential_json_never_carries_long_lived_secrets(env_sample) -> None:
    payload = json.loads(env_sample.credential_json("token", scopes=[DRIVE_SCOPE]))

    assert set(payload) <= {"access_token", "token_type", "expires_at", "scopes", "account"}
    assert "refresh_token" not in payload


async def test_env_sample_missing_connection_fails_before_the_provider_call(
    env_sample,
    variable_service: VariableService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(env_sample.env_key_for(HANDLE), raising=False)
    _ = variable_service

    with pytest.raises(ConnectionUnresolvedError) as excinfo:
        await env_sample.resolve_from_process_environment(HANDLE)

    assert excinfo.value.env_key == "LF_CONNECTION__GOOGLE__WORK"
    assert excinfo.value.code == "connection-unresolved"


def test_env_sample_missing_connection_is_reported_by_the_lfx_run_preflight(
    env_sample,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``lfx run`` aborts before execution; the message names the key, never a value."""
    from types import SimpleNamespace

    from lfx.cli.validation import validate_connection_refs_for_env

    monkeypatch.delenv(env_sample.env_key_for(HANDLE), raising=False)
    vertex = SimpleNamespace(
        data={"node": {"template": {"connection": {"type": "connection_ref", "value": HANDLE}}}},
        params={"connection": HANDLE},
    )
    graph = SimpleNamespace(vertices=[vertex], context={})

    errors = validate_connection_refs_for_env(graph)

    assert [error.env_key for error in errors] == ["LF_CONNECTION__GOOGLE__WORK"]
    assert "LF_CONNECTION__GOOGLE__WORK" in str(errors[0])


# --------------------------------------------------------------------------- #
# secret_manager_resolver.py
# --------------------------------------------------------------------------- #


def _mounted_resolver(secret_sample, tmp_path, payload: str | None = "stored-token"):
    if payload is not None:
        (tmp_path / "google__work").write_text(f"{payload}\n", encoding="utf-8")
    return secret_sample.MountedSecretsConnectionResolver(secrets_dir=str(tmp_path))


async def test_secret_manager_sample_resolves_through_a_callable_client(secret_sample) -> None:
    calls: list[str] = []

    def fake_client(secret_name: str) -> str:
        calls.append(secret_name)
        return "vault-token"

    resolver = secret_sample.SecretManagerConnectionResolver(fetch_secret=fake_client)

    credential = await resolver.resolve(_request())

    assert resolver.ready is True
    assert calls == ["langflow/connections/google/work"]
    assert credential.access_token.get_secret_value() == "vault-token"
    assert credential.owner_kind == "env"


async def test_secret_manager_sample_reads_a_mounted_secret_file(secret_sample, tmp_path) -> None:
    resolver = _mounted_resolver(secret_sample, tmp_path)

    credential = await resolver.resolve(_request())

    # The trailing newline mounted secrets carry is stripped, not sent as part of the token.
    assert credential.access_token.get_secret_value() == "stored-token"


async def test_secret_manager_sample_missing_secret_is_typed_and_names_no_store_detail(
    secret_sample,
    tmp_path,
) -> None:
    resolver = _mounted_resolver(secret_sample, tmp_path, payload=None)

    with pytest.raises(ConnectionUnresolvedError) as excinfo:
        await resolver.resolve(_request())

    assert excinfo.value.env_key is None
    assert str(tmp_path) not in str(excinfo.value)


async def test_secret_manager_sample_rejects_a_refresh_token_payload(secret_sample, tmp_path) -> None:
    payload = json.dumps({"access_token": "token", "refresh_token": "must-not-enter-runtime"})
    resolver = _mounted_resolver(secret_sample, tmp_path, payload=payload)

    with pytest.raises(ValueError, match="refresh_token"):
        await resolver.resolve(_request())


async def test_secret_manager_sample_expired_and_scope_missing_are_typed(secret_sample, tmp_path) -> None:
    expired = json.dumps(
        {
            "access_token": "expired",
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        }
    )
    resolver = _mounted_resolver(secret_sample, tmp_path, payload=expired)
    with pytest.raises(AuthExpiredError):
        await resolver.resolve(_request())

    (tmp_path / "google__work").write_text(
        json.dumps({"access_token": "token", "scopes": []}),
        encoding="utf-8",
    )
    with pytest.raises(ScopeMissingError) as excinfo:
        await resolver.resolve(_request(scopes=frozenset({DRIVE_SCOPE})))
    assert excinfo.value.missing == frozenset({DRIVE_SCOPE})


async def test_secret_manager_sample_denies_non_headless_principals(secret_sample, tmp_path) -> None:
    resolver = _mounted_resolver(secret_sample, tmp_path)

    for principal in (
        ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
        ExecutionPrincipal(kind="anonymous_public"),
        ExecutionPrincipal(kind="unknown"),
    ):
        with pytest.raises(ConnectionNotAuthorizedError):
            await resolver.resolve(_request(principal=principal))


def test_secret_manager_sample_refuses_a_path_that_escapes_the_secrets_directory(secret_sample, tmp_path) -> None:
    resolver = secret_sample.MountedSecretsConnectionResolver(secrets_dir=str(tmp_path / "mounted"))
    (tmp_path / "mounted").mkdir()

    with pytest.raises(ValueError, match="escapes"):
        resolver.fetch_secret("../outside")


def test_secret_manager_sample_without_a_client_fails_loudly(secret_sample) -> None:
    with pytest.raises(NotImplementedError, match="fetch_secret"):
        secret_sample.SecretManagerConnectionResolver().fetch_secret("any")


# --------------------------------------------------------------------------- #
# lfx.toml registration
# --------------------------------------------------------------------------- #


def test_lfx_toml_sample_registers_the_documented_resolver(secret_sample) -> None:
    """The path string in the sample ``lfx.toml`` resolves to a usable resolver."""
    import tomllib

    from tests.unit.services.connection.sample_loader import SAMPLES_DIR

    _ = secret_sample  # importing the sample registers it under its own module name
    config = tomllib.loads((SAMPLES_DIR / "lfx.toml").read_text(encoding="utf-8"))
    path = config["services"]["connection_resolver_service"]
    assert path == "secret_manager_resolver:MountedSecretsConnectionResolver"

    manager = ServiceManager()
    manager._register_service_from_path("connection_resolver_service", path)

    registered = manager.service_classes[
        next(key for key in manager.service_classes if key.value == "connection_resolver_service")
    ]
    assert issubclass(registered, BaseConnectionResolverService)


def test_wrong_resolver_class_fails_closed_instead_of_using_the_env_fallback() -> None:
    manager = ServiceManager()

    with pytest.raises(RuntimeError, match="must subclass BaseConnectionResolverService"):
        manager._register_service_from_path("connection_resolver_service", "builtins:str")


# --------------------------------------------------------------------------- #
# serve_request.sh
# --------------------------------------------------------------------------- #

_CURL_STUB = """#!/usr/bin/env bash
# Stand in for curl: emit the request body the sample would have sent, NUL-terminated
# so a pretty-printed multi-line JSON body stays one record.
prev=""
for arg in "$@"; do
  if [ "$prev" = "-d" ]; then printf '%s\\0' "$arg"; fi
  prev="$arg"
done
"""

requires_shell_tools = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="serve_request.sh needs bash and jq",
)


def _serve_request_bodies(tmp_path) -> list[dict]:
    """Run the sample script with a curl stub and return the bodies it would POST."""
    from tests.unit.services.connection.sample_loader import SAMPLES_DIR

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "curl"
    stub.write_text(_CURL_STUB, encoding="utf-8")
    stub.chmod(0o755)

    served_credential = "served-token"  # pragma: allowlist secret
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "FLOW_ID": "00000000-0000-0000-0000-0000000013a1",
            "LANGFLOW_API_KEY": "int13-test-api-key",  # pragma: allowlist secret
            "GOOGLE_ACCESS_TOKEN": served_credential,
        }
    )
    result = subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SAMPLES_DIR / "serve_request.sh")],
        capture_output=True,
        check=True,
        env=env,
    )
    return [json.loads(record) for record in result.stdout.split(b"\0") if record.strip()]


@requires_shell_tools
async def test_serve_request_sample_sends_credentials_that_actually_resolve(env_sample, tmp_path) -> None:
    """The documented curl bodies resolve; the sample is executed, not just displayed."""
    bare, structured = _serve_request_bodies(tmp_path)

    assert bare["global_vars"] == {"LF_CONNECTION__GOOGLE__WORK": "served-token"}
    credential = await env_sample.resolve_with_request_scope(HANDLE, bare["global_vars"])
    assert credential.access_token.get_secret_value() == "served-token"

    # The JSON body is a JSON-encoded string, not a nested object: runtime_variables
    # json.loads() the value and drops anything that is not a string.
    raw = structured["global_vars"]["LF_CONNECTION__GOOGLE__WORK"]
    assert isinstance(raw, str)
    payload = json.loads(raw)
    assert set(payload) <= {"access_token", "token_type", "expires_at", "scopes", "account"}

    credential = await env_sample.resolve_with_request_scope(
        HANDLE,
        structured["global_vars"],
        required_scopes=[DRIVE_SCOPE],
    )
    assert credential.scopes_verified is True
    assert credential.account is not None
    # A stale literal expiry would make every copy-pasted request fail auth-expired.
    assert credential.expires_at is not None
    assert credential.expires_at > datetime.now(timezone.utc)


def test_samples_never_hardcode_a_timestamp_that_goes_stale() -> None:
    """No sample ships a literal date: expiries are computed when the sample runs."""
    import re

    from tests.unit.services.connection.sample_loader import SAMPLES_DIR

    offenders = {
        path.name: re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", path.read_text(encoding="utf-8"))
        for path in sorted(SAMPLES_DIR.iterdir())
        if path.is_file()
    }
    assert {name: found for name, found in offenders.items() if found} == {}


# --------------------------------------------------------------------------- #
# documentation drift
# --------------------------------------------------------------------------- #


def test_documented_error_codes_match_the_lfx_vocabulary() -> None:
    """The page's error-code table is exactly ``INTEGRATION_ERROR_CODES``.

    The table is the contract a headless host branches on. Pinning it here means a
    new code added to lfx cannot ship undocumented, and the page cannot promise a
    code lfx does not raise.
    """
    import re

    from lfx.integrations import INTEGRATION_ERROR_CODES

    from tests.unit.services.connection.sample_loader import SAMPLES_DIR

    page = (SAMPLES_DIR.parents[1] / "lfx-connections.mdx").read_text(encoding="utf-8")
    table = re.search(r"## Error codes\n(.*?)(?=\n## )", page, flags=re.DOTALL)
    assert table is not None, "lfx-connections.mdx must keep an '## Error codes' section"
    documented = set(re.findall(r"^\| `([a-z-]+)` \|", table.group(1), flags=re.MULTILINE))

    assert documented == set(INTEGRATION_ERROR_CODES)
