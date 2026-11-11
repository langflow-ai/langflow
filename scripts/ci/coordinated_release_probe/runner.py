"""The bounded, offline operator integration exercise."""

# This probe intentionally turns every unexpected injected interaction into a
# machine-readable failed report and uses assertion diagnostics in its doubles.
# ruff: noqa: TRY003, EM101, EM102, B904, BLE001, E501, B023, TC003, ARG005

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import traceback
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.ci.coordinated_release.build import build_result, canonical_digest, validate_request
from scripts.ci.coordinated_release.contract import identity

from .doubles import ArtifactDouble, CosHTTPDouble, PipelineDouble, TokenDouble
from .operator_loader import load_release_package, module, source_snapshot

SHA = "1" * 40
INDEX = "sha256:" + "2" * 64
PLATFORM_DIGEST = "sha256:" + "3" * 64
RUN = {
    "provider": "github",
    "pipeline_id": "coordinated-release.yml",
    "id": "9001",
    "url": "https://github.com/langflow-ai/langflow/actions/runs/9001",
}


class ProbeFailureError(RuntimeError):
    pass


class Report:
    def __init__(self):
        self.supported: list[dict[str, Any]] = []
        self.expected_rejections: list[dict[str, Any]] = []
        self.known_gaps: list[dict[str, Any]] = []

    def add(self, bucket: str, name: str, detail: str, **extra: Any) -> None:
        row = {"name": name, "detail": detail, **extra}
        getattr(self, bucket).append(row)

    def document(self, snapshots: dict[str, Any], base_sha: str) -> dict[str, Any]:
        observed_gaps = [row for row in self.known_gaps if row.get("status", "observed") == "observed"]
        resolved_gaps = [row for row in self.known_gaps if row.get("status") == "not_observed_in_current_operator"]
        return {
            "status": "passed" if not snapshots.get("changed") else "failed",
            "operator": {"base_sha": base_sha, "source": snapshots},
            "supported": self.supported,
            "expected_rejections": self.expected_rejections,
            "known_gaps": self.known_gaps,
            "summary": {
                "supported": len(self.supported),
                "expected_rejections": len(self.expected_rejections),
                "known_gaps": len(self.known_gaps),
                "observed_gaps": len(observed_gaps),
                "resolved_gap_cases": len(resolved_gaps),
            },
        }


def _request(mode: str, candidate: str | None, invocation: str) -> dict[str, Any]:
    version = "1.14.0"
    release_id = identity(version, mode, candidate)
    return {
        "schema_version": 1,
        "coordinator_id": "oss-probe",
        "invocation_id": invocation,
        "component": "oss",
        "version": version,
        "mode": mode,
        "candidate": candidate,
        "release_id": release_id,
        "source": {
            "repository": "https://github.com/langflow-ai/langflow",
            "branch": "release-" + version,
            "commit": SHA,
        },
        "oss_commit": SHA,
        "platforms": ["linux/amd64"],
        "dependencies": {},
        "destination": "registry.test/staging/oss",
    }


def _zip(result: dict[str, Any]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("component-result.json", json.dumps(result, sort_keys=True))
    return data.getvalue()


def _artifact(result: dict[str, Any], *, expired=False, workflow_run_id="9001", digest=None) -> dict[str, Any]:
    return {
        "id": 42,
        "name": "release-result-" + result["invocation_id"],
        "expired": expired,
        "workflow_run": {"id": workflow_run_id},
        "size_in_bytes": len(_zip(result)),
        "digest": digest or "sha256:" + "a" * 64,
    }


def _payload(request: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"request": request, "request_digest": canonical_digest(request), "run": RUN}
    if result is not None:
        payload["result"] = result
    return payload


def run(operator_root: Path) -> dict[str, Any]:
    """Run all checks and return a JSON-serializable report."""
    before = source_snapshot(operator_root)
    report = Report()
    base_sha = str(before["base_sha"])
    after: dict[str, Any] = before
    try:
        with load_release_package(operator_root) as package:
            contract = module(package, "contract")
            pipeline = module(package, "pipeline_client")
            github_artifacts = module(package, "github_artifacts")
            cos_client = module(package, "cos_client")
            deployment = module(package, "deployment_services")

            rc = _request("rc", "rc.1", "oss-probe-rc-1")
            official = _request("official", None, "oss-probe-official")
            rc_digest = canonical_digest(rc)
            official_digest = canonical_digest(official)
            validate_request(rc)
            validate_request(official)
            if contract.digest(rc) != rc_digest or contract.digest(official) != official_digest:
                raise ProbeFailureError("OSS and operator canonical digests differ")
            rc_result = build_result(
                rc,
                rc_digest,
                run_id=RUN["id"],
                run_url=RUN["url"],
                index_digest=INDEX,
                platform_digests={"linux/amd64": PLATFORM_DIGEST},
            )
            official_result = build_result(
                official,
                official_digest,
                run_id=RUN["id"],
                run_url=RUN["url"],
                index_digest=INDEX,
                platform_digests={"linux/amd64": PLATFORM_DIGEST},
            )
            contract.validate_result(rc_result, rc, RUN)
            contract.validate_result(official_result, official, RUN)
            report.add(
                "supported",
                "rc_and_official_contract_compatibility",
                "OSS build helpers and operator validators accepted matching canonical identities and digests",
                release_ids=[rc["release_id"], official["release_id"]],
            )

            # Exercise the actual GitHub dispatch implementation with a strict command double.
            dispatch_io = PipelineDouble(rc["invocation_id"], RUN["id"], RUN["url"])
            client = pipeline.PipelineClient(
                {"components": {"oss": {"pipeline_id": "coordinated-release.yml", "workflow_ref": "main"}}},
                dispatch_io,
                lambda seconds: None,
                None,
            )
            observed_run = client.dispatch(rc)
            dispatch_call = dispatch_io.calls[0]
            dispatch_body = dispatch_call[1]
            expected_envelope = {"request": rc, "request_digest": rc_digest}
            observed_envelope = json.loads(dispatch_body["inputs"]["release_request"])
            if (
                dispatch_body.get("ref") != "main"
                or dispatch_body["inputs"].get("invocation_id") != rc["invocation_id"]
                or observed_envelope != expected_envelope
                or observed_run != RUN
            ):
                raise ProbeFailureError("dispatch envelope, ref, invocation, or run handle changed")
            report.add(
                "supported",
                "github_dispatch_envelope",
                "PipelineClient.dispatch emitted the exact OSS envelope, configured ref, and invocation correlation",
                command=dispatch_call[0],
                ref=dispatch_body["ref"],
                invocation_id=dispatch_body["inputs"]["invocation_id"],
            )
            # Pull and persist the exact run artifact through the actual operator modules.
            archive = _zip(rc_result)
            selected = _artifact(rc_result)
            selected["digest"] = "sha256:" + hashlib.sha256(archive).hexdigest()
            artifact_io = ArtifactDouble(selected, archive)
            payload = _payload(rc)
            settings = {"pipeline_id": "coordinated-release.yml", "workflow_ref": "main"}
            pulled = github_artifacts.fetch_result(payload, artifact_io, settings)
            if pulled != rc_result or selected["name"] != "release-result-" + rc["invocation_id"]:
                raise ProbeFailureError("exact single-file result artifact was not selected")
            with zipfile.ZipFile(io.BytesIO(archive)) as checked:
                if checked.namelist() != ["component-result.json"]:
                    raise ProbeFailureError("result artifact is not a single-file ZIP")
            report.add(
                "supported",
                "exact_run_artifact",
                "github_artifacts.fetch_result selected the exact run artifact and bounded single-file ZIP",
                artifact_name=selected["name"],
                archive_entries=["component-result.json"],
            )
            mismatched_native = dict(artifact_io.native, head_branch="untrusted", run_attempt=99)
            try:
                github_artifacts.fetch_result(
                    payload,
                    ArtifactDouble(selected, archive, native=mismatched_native),
                    settings,
                )
            except contract.ContractError:
                report.add(
                    "known_gaps",
                    "dispatch_workflow_ref_and_attempt_not_bound",
                    "historical wrong-workflow-ref/rerun case is rejected by current github_runs verification",
                    status="not_observed_in_current_operator",
                )
            else:
                report.add(
                    "known_gaps",
                    "dispatch_workflow_ref_and_attempt_not_bound",
                    "fetch_result accepted a native run with an unrelated head ref and run_attempt=99",
                    status="observed",
                )

            store_settings = {
                "type": "cos",
                "endpoint": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
                "bucket": "fixture",
                "prefix": "probe",
            }
            cos_http = CosHTTPDouble()
            token = TokenDouble()
            cos = cos_client.CosClient(store_settings, execute=token, open_url=cos_http)
            backend = SimpleNamespace(execute=artifact_io)
            services = deployment.DeploymentServices(
                {"store": store_settings, "components": {"oss": settings}}, backend, client=cos
            )
            with tempfile.TemporaryDirectory() as temporary:
                stored = services.call("result", payload | {"artifact_directory": temporary})
                if stored != rc_result:
                    raise ProbeFailureError("DeploymentServices did not return the persisted OSS result")
                services.call("save_result", payload | {"result": rc_result, "artifact_directory": temporary})
                result_key = services.artifacts.key(RUN) + "component-result.json"
                raw, _ = cos.get(result_key)
                if raw != json.dumps(rc_result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode():
                    raise ProbeFailureError("COS read bytes differ from the immutable component result")
                puts_before_divergence = cos_http.put_count
                try:
                    cos.immutable(result_key, b"different-result")
                except contract.ContractError:
                    pass
                else:
                    raise ProbeFailureError("COS allowed a divergent immutable save")
                if cos_http.put_count <= puts_before_divergence or cos.get(result_key)[0] != raw:
                    raise ProbeFailureError("COS divergent-save check did not preserve the original bytes")
            report.add(
                "supported",
                "cos_conditional_immutable_store",
                "actual CosClient and CosArtifacts used injected If-None-Match/read doubles; same bytes were idempotent and divergent bytes were rejected",
                put_count=cos_http.put_count,
                credential_commands=len(token.calls),
            )

            # Keep the historical checksum concern explicitly outside the pass/fail
            # safety checks.  The current operator may reject it (the desired fix).
            bad_digest_artifact = _artifact(rc_result, digest="sha256:" + "f" * 64)
            try:
                github_artifacts.fetch_result(
                    payload,
                    ArtifactDouble(bad_digest_artifact, archive),
                    settings,
                )
            except contract.ContractError:
                report.add(
                    "known_gaps",
                    "artifact_checksum_metadata_not_verified",
                    "historical bad-checksum case is rejected by the current operator",
                    status="not_observed_in_current_operator",
                )
            else:
                report.add(
                    "known_gaps",
                    "artifact_checksum_metadata_not_verified",
                    "fetch_result accepted a deliberately wrong GitHub artifact digest metadata value",
                    status="observed",
                )

            # Each malformed input must fail before DeploymentServices can write COS.
            rejection_cases = {
                "malformed_request_digest": payload | {"request_digest": "sha256:bad"},
                "wrong_run_artifact": payload,
                "duplicate_artifacts": payload,
                "expired_artifact": payload,
                "mismatched_result": payload,
            }
            for name, rejected_payload in rejection_cases.items():
                execute = None
                if name == "malformed_request_digest":
                    artifact_case = selected
                    execute = ArtifactDouble(artifact_case, archive)
                else:
                    artifact_case = dict(selected)
                    if name == "wrong_run_artifact":
                        artifact_case["workflow_run"] = {"id": "wrong-run"}
                    elif name == "duplicate_artifacts":
                        execute = ArtifactDouble(artifact_case, archive)
                    elif name == "expired_artifact":
                        artifact_case["expired"] = True
                    elif name == "mismatched_result":
                        mismatched = dict(rc_result, request_digest="sha256:" + "0" * 64)
                        mismatched_archive = _zip(mismatched)
                        artifact_case["size_in_bytes"] = len(mismatched_archive)
                        artifact_case["digest"] = "sha256:" + hashlib.sha256(mismatched_archive).hexdigest()
                        execute = ArtifactDouble(artifact_case, mismatched_archive)
                    if execute is None:
                        execute = ArtifactDouble(artifact_case, archive)
                # The duplicate fixture intentionally returns two records.
                if name == "duplicate_artifacts":
                    original = execute

                    def duplicate_call(args, **options):
                        result = original(args, **options)
                        if not options.get("raw") and str(args[-1]).endswith("/artifacts?per_page=100"):
                            return [{"artifacts": [dict(original.artifact), dict(original.artifact)]}]
                        return result

                    execute = duplicate_call
                cos_case_http = CosHTTPDouble()
                case_token = TokenDouble()
                case_cos = cos_client.CosClient(store_settings, execute=case_token, open_url=cos_case_http)
                case_backend = SimpleNamespace(execute=execute)
                case_services = deployment.DeploymentServices(
                    {"store": store_settings, "components": {"oss": settings}},
                    case_backend,
                    client=case_cos,
                )
                try:
                    case_services.call("result", rejected_payload)
                except contract.ContractError:
                    if cos_case_http.put_count != 0:
                        raise ProbeFailureError(f"{name} wrote COS before rejection")
                    report.add("expected_rejections", name, "operator rejected input before any COS PUT")
                else:
                    raise ProbeFailureError(f"operator accepted {name}")
                execute = None

            native_cases = {
                "wrong_native_ref": dict(artifact_io.native, head_branch="untrusted"),
                "wrong_native_title": dict(artifact_io.native, display_title="other-invocation"),
                "wrong_native_attempt": dict(artifact_io.native, run_attempt=99),
                "wrong_native_workflow": dict(artifact_io.native, workflow_id=701),
            }
            for name, native in native_cases.items():
                native_io = ArtifactDouble(selected, archive, native=native)
                native_http = CosHTTPDouble()
                native_cos = cos_client.CosClient(
                    store_settings,
                    execute=TokenDouble(),
                    open_url=native_http,
                )
                native_services = deployment.DeploymentServices(
                    {"store": store_settings, "components": {"oss": settings}},
                    SimpleNamespace(execute=native_io),
                    client=native_cos,
                )
                try:
                    native_services.call("result", payload)
                except contract.ContractError:
                    if native_http.put_count != 0:
                        raise ProbeFailureError(f"{name} wrote COS before rejection")
                    report.add("expected_rejections", name, "native identity rejected before any COS PUT")
                else:
                    report.add(
                        "known_gaps",
                        name,
                        "fetch_result accepted a native run identity mismatch",
                        status="observed",
                    )

            # Demonstrate the current replay behavior after a successful durable save.
            expired_io = ArtifactDouble(dict(selected, expired=True), archive)
            backend.execute = expired_io
            try:
                replay = services.call("result", payload)
            except contract.ContractError:
                durable = services.artifacts.read(payload)
                if durable != rc_result:
                    raise ProbeFailureError("expired-artifact replay also lost the durable COS result")
                report.add(
                    "known_gaps",
                    "expired_github_artifact_blocks_result_replay",
                    "DeploymentServices.result re-fetched an expired GitHub artifact instead of recovering the durable COS result",
                    status="observed",
                )
            else:
                if replay != rc_result:
                    raise ProbeFailureError("expired-artifact replay returned the wrong durable result")
                if expired_io.calls:
                    raise ProbeFailureError("durable replay unexpectedly contacted GitHub")
                report.add(
                    "known_gaps",
                    "expired_github_artifact_blocks_result_replay",
                    "historical expired-artifact replay case is recovered from COS by the current operator",
                    status="not_observed_in_current_operator",
                )
    except Exception as error:
        report.add(
            "expected_rejections",
            "probe_execution",
            f"unexpected probe failure: {error!r}\n{traceback.format_exc()}",
        )
        report_status = "failed"
    else:
        report_status = "passed"
    try:
        after = source_snapshot(operator_root)
    except Exception as error:
        after = {"error": str(error), "changed": True}
    changed = before.get("files") != after.get("files") or before.get("base_sha") != after.get("base_sha")
    snapshots = {"before": before, "after": after, "changed": changed}
    output = report.document(snapshots, base_sha)
    if report_status == "failed" or changed:
        output["status"] = "failed"
    return output
