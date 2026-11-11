"""Focused Contract v1 tests for the OSS coordinated workflow."""

# ruff: noqa: S603, S607

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.coordinated_release.build import (
    ContractError,
    build_result,
    canonical_digest,
    package_version,
    parse_envelope,
    validate_provenance,
    validate_request,
)

SOURCE_SHA = "a" * 40
INDEX_DIGEST = "sha256:" + "1" * 64
AMD_DIGEST = "sha256:" + "2" * 64
ARM_DIGEST = "sha256:" + "3" * 64


def request(**overrides):
    value = {
        "schema_version": 1,
        "coordinator_id": "release-1-14-0-rc1",
        "invocation_id": "release-1-14-0-rc1-oss-1",
        "component": "oss",
        "version": "1.14.0",
        "candidate": "rc.1",
        "mode": "rc",
        "release_id": "1.14.0-rc.1",
        "source": {
            "repository": "https://github.com/langflow-ai/langflow",
            "branch": "release-1.14.0",
            "commit": SOURCE_SHA,
        },
        "oss_commit": SOURCE_SHA,
        "platforms": ["linux/amd64", "linux/arm64/v8"],
        "dependencies": {},
        "destination": "registry.example/langflow-staging",
    }
    value.update(overrides)
    return value


def test_rc_and_official_package_versions():
    assert package_version("1.14.0", "rc", "rc.1") == "1.14.0rc1"
    assert package_version("1.14.0", "official", None) == "1.14.0"


def test_envelope_requires_exact_invocation_and_request_hash():
    value = request()
    raw = json.dumps({"request": value, "request_digest": canonical_digest(value)})
    parsed, digest = parse_envelope(raw, value["invocation_id"])
    assert parsed == value
    assert digest == canonical_digest(value)
    with pytest.raises(ContractError, match="invocation_id mismatch"):
        parse_envelope(raw, "another-invocation")
    with pytest.raises(ContractError, match="request_digest mismatch"):
        parse_envelope(json.dumps({"request": value, "request_digest": "sha256:" + "0" * 64}), value["invocation_id"])
    with pytest.raises(ContractError, match="invalid release envelope fields"):
        parse_envelope(
            json.dumps({"request": value, "request_digest": canonical_digest(value), "unexpected": True}),
            value["invocation_id"],
        )
    with pytest.raises(ContractError, match="build request must be an object"):
        parse_envelope(json.dumps({"request": [], "request_digest": canonical_digest(value)}), value["invocation_id"])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {
                "source": {
                    "repository": "https://github.com/langflow-ai/langflow",
                    "branch": "release-1.14.0",
                    "commit": "b" * 39,
                }
            },
            "invalid frozen source",
        ),
        ({"oss_commit": "c" * 40}, "OSS source and oss_commit differ"),
        ({"dependencies": {"oss": {}}}, "wrong dependencies"),
        ({"platforms": ["linux/amd64", "linux/amd64"]}, "duplicate platforms"),
    ],
)
def test_malformed_request_is_rejected(change, message):
    value = request(**change)
    with pytest.raises(ContractError, match=message):
        validate_request(value)


def test_result_carries_native_run_identity_and_provenance():
    value = request()
    digest = canonical_digest(value)
    labels = {
        "org.opencontainers.image.revision": SOURCE_SHA,
        "org.opencontainers.image.version": value["release_id"],
        "langflow.org/release-request": digest,
    }
    result = build_result(
        value,
        digest,
        run_id="9876",
        run_url="https://github.com/langflow-ai/langflow/actions/runs/9876",
        index_digest=INDEX_DIGEST,
        platform_digests={"linux/amd64": AMD_DIGEST, "linux/arm64/v8": ARM_DIGEST},
        labels=labels,
    )
    assert result["run"] == {
        "provider": "github",
        "pipeline_id": "coordinated-release.yml",
        "id": "9876",
        "url": "https://github.com/langflow-ai/langflow/actions/runs/9876",
    }
    assert result["packaging"] == {"version": "1.14.0-rc.1", "python_version": "1.14.0rc1", "smoke_passed": True}
    assert result["publication"] == "staged"
    with pytest.raises(ContractError, match="provenance"):
        validate_provenance(
            {**labels, "org.opencontainers.image.version": "1.14.0"}, SOURCE_SHA, value["release_id"], digest
        )


def test_result_rejects_missing_platform_digest():
    value = request()
    digest = canonical_digest(value)
    labels = {
        "org.opencontainers.image.revision": SOURCE_SHA,
        "org.opencontainers.image.version": value["release_id"],
        "langflow.org/release-request": digest,
    }
    with pytest.raises(ContractError, match="platform digest matrix"):
        build_result(
            value,
            digest,
            run_id="1",
            run_url="https://example.test/run/1",
            index_digest=INDEX_DIGEST,
            platform_digests={"linux/amd64": AMD_DIGEST},
            labels=labels,
        )


def test_staging_allowlist_does_not_accept_customer_override():
    from scripts.ci.coordinated_release.execution import validate_staging_destination

    validate_staging_destination("registry.example/langflow-staging", "registry.example/langflow-staging")
    with pytest.raises(ContractError, match="not allowlisted"):
        validate_staging_destination("registry.example/customer", "registry.example/langflow-staging")


def test_verify_checkout_requires_the_exact_git_revision():
    from scripts.ci.coordinated_release.execution import verify_checkout

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path.cwd(), check=True, capture_output=True, text=True
    ).stdout.strip()
    verify_checkout(Path.cwd(), revision)
    with pytest.raises(ContractError, match="source checkout mismatch"):
        verify_checkout(Path.cwd(), "b" * 40)


def test_cli_commands_cover_validation_packaging_lock_reservation_result_and_smoke(tmp_path):
    request_value = request()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request_value))
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "pipeline_id": "coordinated-release.yml",
                "id": "123",
                "url": "https://github.com/langflow-ai/langflow/actions/runs/123",
            }
        )
    )
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({"request": request_value, "request_digest": canonical_digest(request_value)}))

    def invoke(*args, env=None, check=True):
        return subprocess.run(
            [sys.executable, "-m", "scripts.ci.coordinated_release.build", *args],
            cwd=Path.cwd(),
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )

    assert json.loads(
        invoke(
            "validate", "--request-file", str(envelope_path), "--invocation-id", request_value["invocation_id"]
        ).stdout
    )["request_digest"] == canonical_digest(request_value)
    assert json.loads(invoke("version", "--request-file", str(request_path)).stdout)["python_version"] == "1.14.0rc1"

    source = tmp_path / "source"
    (source / "src/backend/base").mkdir(parents=True)
    (source / "src/frontend").mkdir()
    (source / "pyproject.toml").write_text('version = "1.13.2"\ndependencies = ["langflow-base==1.13.2"]\n')
    (source / "src/backend/base/pyproject.toml").write_text('version = "1.13.2"\n')
    (source / "src/frontend/package.json").write_text('{"name":"langflow","version":"1.13.2"}\n')
    (source / "src/frontend/package-lock.json").write_text(
        '{"version":"1.13.2","packages":{"":{"version":"1.13.2"}}}\n'
    )
    (source / "uv.lock").write_text(
        '[[package]]\nname = "langflow"\nversion = "1.13.2"\n\n'
        '[[package]]\nname = "langflow-base"\nversion = "1.13.2"\n'
    )
    invoke("materialize", "--source", str(source), "--release-id", "1.14.0-rc.1", "--python-version", "1.14.0rc1")
    invoke("lock", "--source", str(source), "--python-version", "1.14.0rc1")
    assert 'version = "1.14.0rc1"' in (source / "uv.lock").read_text()
    assert json.loads((source / "src/frontend/package.json").read_text())["version"] == "1.14.0-rc.1"
    assert (source / "src/frontend/public/coordinated-release-version.txt").read_text().strip() == "1.14.0-rc.1"

    reserve_script = tmp_path / "reserve.py"
    reserve_script.write_text(
        "import os, sys; from pathlib import Path; data=sys.stdin.read(); "
        "assert '\"request\"' in data and '\"run\"' in data; "
        "Path(os.environ['ADAPTER_MARKER']).write_text('called'); print('true')\n"
    )
    adapter_marker = tmp_path / "adapter-called"
    reserve_env = dict(os.environ, ADAPTER_MARKER=str(adapter_marker))

    def invoke_reserve(run_file, *, check=True):
        return invoke(
            "reserve",
            "--command",
            json.dumps([sys.executable, str(reserve_script)]),
            "--allowlist",
            request_value["destination"],
            "--destination",
            request_value["destination"],
            "--request-file",
            str(request_path),
            "--run-file",
            str(run_file),
            env=reserve_env,
            check=check,
        )

    invoke_reserve(run_path)
    assert adapter_marker.read_text() == "called"

    invalid_runs = {
        "missing-id": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "url": "https://github.com/langflow-ai/langflow/actions/runs/123",
        },
        "nonnumeric-id": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "id": "abc",
            "url": "https://github.com/langflow-ai/langflow/actions/runs/abc",
        },
        "zero-id": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "id": "0",
            "url": "https://github.com/langflow-ai/langflow/actions/runs/0",
        },
        "leading-zero-id": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "id": "0123",
            "url": "https://github.com/langflow-ai/langflow/actions/runs/0123",
        },
        "wrong-repository": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "id": "123",
            "url": "https://github.example.com/langflow-ai/langflow/actions/runs/123",
        },
        "mismatched-id-url": {
            "provider": "github",
            "pipeline_id": "coordinated-release.yml",
            "id": "123",
            "url": "https://github.com/langflow-ai/langflow/actions/runs/456",
        },
    }
    for name, invalid_run in invalid_runs.items():
        invalid_path = tmp_path / f"run-{name}.json"
        invalid_path.write_text(json.dumps(invalid_run))
        adapter_marker.unlink(missing_ok=True)
        rejected_reservation = invoke_reserve(invalid_path, check=False)
        assert rejected_reservation.returncode == 2
        assert not adapter_marker.exists()

    deny_script = tmp_path / "deny.py"
    deny_script.write_text("print('false')\n")
    denied = invoke(
        "reserve",
        "--command",
        json.dumps([sys.executable, str(deny_script)]),
        "--allowlist",
        request_value["destination"],
        "--destination",
        request_value["destination"],
        "--request-file",
        str(request_path),
        "--run-file",
        str(run_path),
        check=False,
    )
    assert denied.returncode == 2
    assert "unique reservation" in denied.stderr

    image_path = tmp_path / "image.json"
    image_path.write_text(
        json.dumps(
            {
                "repository": request_value["destination"],
                "tag": request_value["release_id"],
                "digest": INDEX_DIGEST,
                "platforms": {"linux/amd64": AMD_DIGEST, "linux/arm64/v8": ARM_DIGEST},
            }
        )
    )
    result_path = tmp_path / "result.json"
    invoke(
        "result",
        "--request-file",
        str(request_path),
        "--run-id",
        "123",
        "--run-url",
        "https://github.com/langflow-ai/langflow/actions/runs/123",
        "--image",
        str(image_path),
        "--output",
        str(result_path),
    )
    assert json.loads(result_path.read_text())["status"] == "succeeded"

    mismatched_image = tmp_path / "mismatched-image.json"
    mismatched_image.write_text(
        json.dumps(
            {
                **json.loads(image_path.read_text()),
                "repository": "registry.example/other-staging",
            }
        )
    )
    rejected = invoke(
        "result",
        "--request-file",
        str(request_path),
        "--run-id",
        "123",
        "--run-url",
        "https://github.com/langflow-ai/langflow/actions/runs/123",
        "--image",
        str(mismatched_image),
        "--output",
        str(tmp_path / "rejected.json"),
        check=False,
    )
    assert rejected.returncode == 2
    assert "image repository differs" in rejected.stderr

    docker = tmp_path / "docker"
    docker_log = tmp_path / "docker.log"
    docker.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> "$DOCKER_LOG"\n'
        'if [ "${DOCKER_FAIL_RUN:-0}" = 1 ] && [ "$1" = run ]; then exit 42; fi\n'
        "exit 0\n"
    )
    docker.chmod(0o755)
    smoke_env = dict(
        os.environ,
        PATH=f"{tmp_path}:{os.environ.get('PATH', '')}",
        DOCKER_LOG=str(docker_log),
    )
    invoke("smoke", "--image-record", str(image_path), "--python-version", "1.14.0rc1", env=smoke_env)
    commands = [shlex.split(line) for line in docker_log.read_text().splitlines()]
    pulls = [command for command in commands if command[0] == "pull"]
    runs = [command for command in commands if command[0] == "run"]
    removals = [command for command in commands if command[:2] == ["rm", "-f"]]
    assert [command[-1] for command in pulls] == [
        request_value["destination"] + "@" + AMD_DIGEST,
        request_value["destination"] + "@" + ARM_DIGEST,
    ]
    names = [command[command.index("--name") + 1] for command in runs]
    assert len(names) == 4
    assert len(set(names)) == len(names)
    assert all(name.startswith("lf-coordinated-smoke-") for name in names)
    assert set(names) == {command[-1] for command in removals}
    assert any("--entrypoint python" in line for line in docker_log.read_text().splitlines())
    assert any("--entrypoint langflow" in line for line in docker_log.read_text().splitlines())

    failure_log = tmp_path / "docker-failure.log"
    failure_env = dict(smoke_env, DOCKER_LOG=str(failure_log), DOCKER_FAIL_RUN="1")
    failed = invoke(
        "smoke", "--image-record", str(image_path), "--python-version", "1.14.0rc1", env=failure_env, check=False
    )
    assert failed.returncode == 2
    failure_commands = [shlex.split(line) for line in failure_log.read_text().splitlines()]
    failure_runs = [command for command in failure_commands if command[0] == "run"]
    failure_removals = [command for command in failure_commands if command[:2] == ["rm", "-f"]]
    assert len(failure_runs) == 1
    failed_name = failure_runs[0][failure_runs[0].index("--name") + 1]
    removed_names = {command[-1] for command in failure_removals}
    assert failed_name in removed_names
    assert len(removed_names) == 2
