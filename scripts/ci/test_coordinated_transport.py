"""Exercise exact-run artifact ingress with real ZIP bytes and isolated stores."""

import copy
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts.ci.coordinated_release.contract import ContractError, digest
from scripts.ci.coordinated_release.transport import GitHubArtifacts, transfer


@pytest.fixture
def evidence():
    request = {
        "schema_version": 1,
        "coordinator_id": "fixture",
        "invocation_id": "fixture-oss-1",
        "component": "oss",
        "version": "1.14.0",
        "candidate": "rc.1",
        "mode": "rc",
        "release_id": "1.14.0-rc.1",
        "source": {
            "repository": "https://github.com/langflow-ai/langflow",
            "branch": "release-1.14.0",
            "commit": "a" * 40,
        },
        "oss_commit": "a" * 40,
        "platforms": ["linux/amd64"],
        "dependencies": {},
        "destination": "registry.test/staging/oss",
    }
    run = {
        "provider": "github",
        "pipeline_id": "coordinated-release.yml",
        "id": "123",
        "url": "https://github.com/langflow-ai/langflow/actions/runs/123",
    }
    result = {
        "schema_version": 1,
        "request_digest": digest(request),
        "invocation_id": request["invocation_id"],
        "component": "oss",
        "source_commit": "a" * 40,
        "oss_commit": "a" * 40,
        "release_id": request["release_id"],
        "status": "succeeded",
        "run": run,
        "image": {
            "repository": request["destination"],
            "tag": request["release_id"],
            "digest": "sha256:" + "b" * 64,
            "platforms": {"linux/amd64": "sha256:" + "c" * 64},
        },
        "publication": "staged",
        "packaging": {"version": request["release_id"], "smoke_passed": True},
    }
    payload = {"request": request, "request_digest": digest(request), "run": run}
    native = {
        "id": 123,
        "html_url": run["url"],
        "repository": {"full_name": "langflow-ai/langflow"},
        "workflow_id": 42,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "display_title": request["invocation_id"],
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
    }
    return payload, result, native


def archive_bytes(result, name="component-result.json"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, json.dumps(result))
    return buffer.getvalue()


class FixtureGitHub(GitHubArtifacts):
    def __init__(self, evidence, *, member="component-result.json"):
        self.payload, self.result, self.native = copy.deepcopy(evidence)
        self.data = archive_bytes(self.result, member)
        self.artifact = {
            "id": 99,
            "name": "release-result-fixture-oss-1",
            "expired": False,
            "workflow_run": {"id": 123},
            "size_in_bytes": len(self.data),
            "digest": "sha256:" + hashlib.sha256(self.data).hexdigest(),
        }
        self.items = [self.artifact]
        self.calls = []

    def get(self, endpoint, *, binary=False):
        self.calls.append(endpoint)
        if endpoint == "actions/runs/123":
            return self.native
        if endpoint == "actions/workflows/coordinated-release.yml":
            return {"id": 42, "path": ".github/workflows/coordinated-release.yml"}
        if endpoint == "actions/runs/123/artifacts?per_page=100&page=1":
            return {"artifacts": self.items}
        if endpoint == "actions/artifacts/99/zip":
            assert binary
            return self.data
        raise AssertionError(endpoint)


def test_transfer_persists_exact_result_and_repeated_save_is_idempotent(evidence, tmp_path):
    github = FixtureGitHub(evidence)
    payload, result, _ = evidence
    target = tmp_path / "component-result.json"
    calls_before_cached_transfer = None

    def store(argv, value):
        if argv == ["save"]:
            if target.exists():
                assert json.loads(target.read_text()) == value["result"]
            else:
                target.write_text(json.dumps(value["result"]))
            return True
        assert argv == ["read"]
        assert value == payload
        return json.loads(target.read_text()) if target.exists() else None

    assert transfer(payload, store_read=["read"], store_save=["save"], github=github, command=store) == result
    calls_before_cached_transfer = list(github.calls)
    assert transfer(payload, store_read=["read"], store_save=["save"], github=github, command=store) == result
    assert github.calls == calls_before_cached_transfer
    assert all("latest" not in call for call in github.calls)


def test_valid_cached_result_does_not_call_github(evidence):
    payload, result, _ = evidence
    calls = []

    def store(argv, _value):
        calls.append(argv)
        assert argv == ["read"]
        return result

    assert (
        transfer(
            payload,
            store_read=["read"],
            store_save=["save"],
            github=FixtureGitHub(evidence),
            command=store,
        )
        == result
    )
    assert calls == [["read"]]


def test_missing_cached_result_fetches_then_saves_and_reads(evidence):
    payload, result, _ = evidence
    github = FixtureGitHub(evidence)
    calls = []
    saved = []

    def store(argv, value):
        calls.append(argv)
        if argv == ["read"]:
            return None if not saved else saved[0]
        assert argv == ["save"]
        saved.append(value["result"])
        return True

    assert transfer(payload, store_read=["read"], store_save=["save"], github=github, command=store) == result
    assert calls == [["read"], ["save"], ["read"]]
    assert saved == [result]
    assert github.calls


def test_store_read_error_never_falls_back_to_github(evidence):
    calls = []

    def store(argv, _value):
        calls.append(argv)
        raise ContractError("protected store unavailable")

    github = FixtureGitHub(evidence)
    with pytest.raises(ContractError, match="store unavailable"):
        transfer(evidence[0], store_read=["read"], store_save=["save"], github=github, command=store)
    assert calls == [["read"]]
    assert github.calls == []


def test_invalid_cached_result_never_falls_back_to_github(evidence):
    payload, result, _ = evidence
    invalid = copy.deepcopy(result)
    invalid["request_digest"] = "sha256:" + "0" * 64
    calls = []

    def store(argv, _value):
        calls.append(argv)
        return invalid

    github = FixtureGitHub(evidence)
    with pytest.raises(ContractError, match="result mismatch"):
        transfer(payload, store_read=["read"], store_save=["save"], github=github, command=store)
    assert calls == [["read"]]
    assert github.calls == []


def test_cached_result_does_not_bypass_native_run_identity(evidence):
    payload, result, _ = evidence
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["run"]["url"] = "https://github.com/langflow-ai/langflow/actions/runs/124"
    calls = []

    def store(argv, _value):
        calls.append(argv)
        return result

    with pytest.raises(ContractError, match="wrong run URL"):
        transfer(invalid_payload, store_read=["read"], store_save=["save"], command=store)
    assert calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("conclusion", "failure"),
        ("conclusion", "cancelled"),
        ("conclusion", "skipped"),
        ("status", "in_progress"),
        ("display_title", "different-oss-1"),
        ("run_attempt", 2),
        ("head_branch", "untrusted-branch"),
        ("workflow_id", 23),
        ("event", "push"),
        ("id", 124),
    ],
)
def test_native_failure_or_wrong_correlation_never_downloads(evidence, field, value):
    github = FixtureGitHub(evidence)
    github.native[field] = value
    with pytest.raises(ContractError):
        github.fetch(evidence[0]["request"], evidence[0]["run"], workflow_ref="main")
    assert not any("artifacts" in call for call in github.calls)


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "expired", "wrong_run", "checksum", "traversal", "wrong_source"]
)
def test_artifact_failures_are_not_success(evidence, fault):
    github = FixtureGitHub(
        evidence, member="../component-result.json" if fault == "traversal" else "component-result.json"
    )
    if fault == "missing":
        github.items = []
    elif fault == "duplicate":
        github.items.append(copy.deepcopy(github.artifact))
    elif fault == "expired":
        github.artifact["expired"] = True
    elif fault == "wrong_run":
        github.artifact["workflow_run"]["id"] = 124
    elif fault == "checksum":
        github.data += b"changed"
    elif fault == "wrong_source":
        github.result["source_commit"] = "d" * 40
        github.data = archive_bytes(github.result)
        github.artifact["digest"] = "sha256:" + hashlib.sha256(github.data).hexdigest()
    with pytest.raises(ContractError):
        github.fetch(evidence[0]["request"], evidence[0]["run"], workflow_ref="main")


def test_ingress_requires_store_acknowledgement(evidence):
    def store(argv, _value):
        return None if argv == ["read"] else False

    with pytest.raises(ValueError, match="acknowledge"):
        transfer(
            evidence[0],
            store_read=["read"],
            store_save=["save"],
            github=FixtureGitHub(evidence),
            command=store,
        )


def test_request_tampering_fails_before_network_or_store(evidence):
    evidence[0]["request"]["version"] = "1.14.1"
    with pytest.raises(ValueError, match="digest"):
        transfer(
            evidence[0], store_read=["read"], store_save=["save"], command=lambda *_: pytest.fail("unexpected command")
        )


def test_sps_result_uses_existing_protected_store(evidence):
    payload = copy.deepcopy(evidence[0])
    payload["request"]["component"] = "ibm"
    payload["request_digest"] = digest(payload["request"])
    seen = []

    def store(argv, data):
        seen.append((argv, data))
        return {"from": "operator-store"}

    assert transfer(payload, store_read=["read"], store_save=["save"], command=store) == {"from": "operator-store"}
    assert seen == [(["read"], payload)]


def test_workflow_upload_is_consumable_by_exact_run_transport(evidence):
    """Use the producer's actual archive paths to catch ingress incompatibility."""
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/coordinated-release.yml").read_text()
    )
    upload = next(
        step["with"]
        for step in workflow["jobs"]["build"]["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
        and step.get("with", {}).get("name", "").startswith("release-result-")
    )
    assert workflow["run-name"] == "${{ inputs.invocation_id }}"
    name = upload["name"].replace("${{ inputs.invocation_id }}", evidence[0]["request"]["invocation_id"])
    github = FixtureGitHub(evidence)
    members = upload["path"].splitlines()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for member in members:
            archive.writestr(member.strip(), json.dumps(evidence[1]))
    github.data = buffer.getvalue()
    github.artifact.update(name=name, digest="sha256:" + hashlib.sha256(github.data).hexdigest())
    assert github.fetch(evidence[0]["request"], evidence[0]["run"], workflow_ref="main") == evidence[1]
    assert upload.get("overwrite", False) is False
    assert upload["retention-days"] == 90


def test_workflow_retention_guard_accepts_only_public_maximum():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/coordinated-release.yml").read_text()
    )
    step = next(s for s in workflow["jobs"]["build"]["steps"] if s["name"] == "Validate result artifact retention")
    assert "env" not in step
    assert "vars.GITHUB_RETENTION_DAYS" not in step["run"]
    script = step["run"]
    for value in ("1", "", "abc"):
        environment = dict(os.environ, GITHUB_RETENTION_DAYS=value)
        rejected = subprocess.run(  # noqa: S603 - execute the workflow's extracted guard fixture.
            ["bash", "-euo", "pipefail", "-c", script],  # noqa: S607
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert rejected.returncode != 0, value
    accepted = subprocess.run(  # noqa: S603 - execute the workflow's extracted guard fixture.
        ["bash", "-euo", "pipefail", "-c", script],  # noqa: S607
        env=dict(os.environ, GITHUB_RETENTION_DAYS="90"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr


def test_workflow_checkout_verifier_executes_and_rejects_a_different_sha(tmp_path):
    """Execute the workflow's Python verifier against a real read-only checkout."""
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/coordinated-release.yml").read_text())
    step = next(s for s in workflow["jobs"]["build"]["steps"] if s["name"] == "Check out exact requested source SHA")
    line = next(line for line in step["run"].splitlines() if "verify_checkout" in line)
    arguments = shlex.split(line)
    script = arguments[arguments.index("-c") + 1]
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()  # noqa: S607
    (tmp_path / "source").symlink_to(root, target_is_directory=True)
    env = dict(os.environ, PYTHONPATH=str(root / "scripts/ci"), SOURCE_COMMIT=source_sha)
    actual = subprocess.run(  # noqa: S603 - execute the repository's verifier, with no credential/bootstrap access.
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert actual.returncode == 0, actual.stderr
    env["SOURCE_COMMIT"] = "0" * 40
    mismatch = subprocess.run(  # noqa: S603 - same read-only verifier against an intentionally wrong fixture SHA.
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert mismatch.returncode != 0
    assert "source checkout mismatch" in mismatch.stderr
