"""Pull one immutable OSS result into the coordinator's protected result store.

Run on the coordinator worker with an Actions-read GitHub credential. Public
workers upload a run artifact and never receive the private evidence-store key.
"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile

from .contract import ContractError, digest, require, validate_request, validate_result, validate_run

REPOSITORY = "langflow-ai/langflow"
WORKFLOW = "coordinated-release.yml"
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_RESULT = 1024 * 1024
PAGE_SIZE = 100
MAX_PAGES = 100


def _validate_oss_run(run):
    """Validate the coordinator run handle before any external read."""
    validate_run(run)
    run_id = run["id"]
    require(run["provider"] == "github", "wrong OSS run provider")
    require(run["pipeline_id"] == WORKFLOW, "wrong OSS pipeline")
    require(re.fullmatch(r"[1-9][0-9]*", run_id), "invalid run ID")
    require(run["url"] == f"https://github.com/{REPOSITORY}/actions/runs/{run_id}", "wrong run URL")
    return run


def execute(argv, data=None, *, binary=False):
    """Execute a configured argument array without a shell or credential logging."""
    require(isinstance(argv, list) and argv and all(isinstance(a, str) and a for a in argv), "command array required")
    completed = subprocess.run(  # noqa: S603 - argv comes from protected worker configuration, never the request.
        argv,
        input=None if data is None else json.dumps(data).encode(),
        capture_output=True,
        check=False,
        timeout=120,
    )
    require(completed.returncode == 0, "result transport command failed; inspect protected worker logs")
    return completed.stdout if binary else json.loads(completed.stdout)


class GitHubArtifacts:
    """Read only endpoints derived from the fixed repository and native handle."""

    def __init__(self, command=execute):
        self.command = command

    def get(self, endpoint, *, binary=False):
        return self.command(
            ["gh", "api", "--hostname", "github.com", "--method", "GET", f"repos/{REPOSITORY}/{endpoint}"],
            binary=binary,
        )

    def fetch(self, request, run, *, workflow_ref):
        """Verify native success/correlation before downloading exactly one result."""
        _validate_oss_run(run)
        native = self.get(f"actions/runs/{run['id']}")
        workflow = self.get(f"actions/workflows/{WORKFLOW}")
        require(str(native.get("id")) == run["id"] and native.get("html_url") == run["url"], "native run mismatch")
        require(native.get("repository", {}).get("full_name") == REPOSITORY, "wrong run repository")
        require(
            native.get("workflow_id") == workflow.get("id") and workflow.get("path") == f".github/workflows/{WORKFLOW}",
            "wrong workflow",
        )
        require(
            native.get("event") == "workflow_dispatch" and native.get("head_branch") == workflow_ref,
            "untrusted workflow ref/event",
        )
        require(native.get("display_title") == request["invocation_id"], "invocation correlation mismatch")
        require(native.get("run_attempt") == 1, "rerun identity is ambiguous; dispatch a coordinator retry")
        require(
            native.get("status") == "completed" and native.get("conclusion") == "success", "native run did not succeed"
        )

        name = "release-result-" + request["invocation_id"]
        found = []
        for page in range(1, MAX_PAGES + 1):
            response = self.get(f"actions/runs/{run['id']}/artifacts?per_page={PAGE_SIZE}&page={page}")
            artifacts = response["artifacts"]
            found.extend(a for a in artifacts if a.get("name") == name)
            if len(artifacts) < PAGE_SIZE:
                break
        else:
            message = "artifact listing exceeds bounded pagination"
            raise ContractError(message)
        require(len(found) == 1, "missing or duplicate immutable result artifact")
        artifact = found[0]
        require(artifact.get("expired") is False, "result artifact expired before transfer")
        require(str(artifact.get("workflow_run", {}).get("id")) == run["id"], "artifact belongs to another run")
        require(type(artifact.get("id")) is int and artifact["id"] > 0, "invalid artifact ID")
        require(
            type(artifact.get("size_in_bytes")) is int and 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE,
            "oversized result artifact",
        )
        data = self.get(f"actions/artifacts/{artifact['id']}/zip", binary=True)
        require(len(data) <= MAX_ARCHIVE, "oversized downloaded artifact")
        require("sha256:" + hashlib.sha256(data).hexdigest() == artifact.get("digest"), "artifact checksum mismatch")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            require(
                len(members) == 1 and members[0].filename == "component-result.json",
                "unexpected result archive members",
            )
            require(0 < members[0].file_size <= MAX_RESULT, "oversized component result")
            result = json.loads(archive.read(members[0]))
        validate_result(result, request, run)
        return result


def transfer(payload, *, store_read, store_save, workflow_ref="main", github=None, command=execute):
    """Multiplex OSS ingress and the existing SPS filesystem result reader.

    For OSS, ``store_read`` is an authenticated durable lookup: JSON ``null``
    is the only confirmed-absence response. Any command error or non-null
    invalid result is terminal and must never trigger a GitHub fallback.
    """
    request, run = payload["request"], payload["run"]
    require(payload.get("request_digest") == digest(request), "request digest mismatch")
    if request.get("component") != "oss":
        # The operator's existing reader applies its complete component contract.
        return command(store_read, payload)
    validate_request(request)
    _validate_oss_run(run)
    cached = command(store_read, payload)
    if cached is not None:
        require(isinstance(cached, dict), "stored result must be an object")
        validate_result(cached, request, run)
        return cached
    result = (github or GitHubArtifacts(command)).fetch(request, run, workflow_ref=workflow_ref)
    require(
        command(store_save, {"request": request, "run": run, "result": result}) is True,
        "evidence store did not acknowledge immutable save",
    )
    saved = command(store_read, payload)
    require(saved == result, "persisted result differs from downloaded result")
    return saved


def main(argv=None):
    """Use as the coordinator's result bridge; all command values are trusted config."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-read", type=json.loads, required=True)
    parser.add_argument("--store-save", type=json.loads, required=True)
    parser.add_argument("--workflow-ref", default="main")
    args = parser.parse_args(argv)
    result = transfer(
        json.load(sys.stdin), store_read=args.store_read, store_save=args.store_save, workflow_ref=args.workflow_ref
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
