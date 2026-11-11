"""Strict command, GitHub, and COS doubles used by the offline probe."""

# These doubles intentionally raise rich assertion diagnostics for unexpected
# I/O; the probe is a standalone executable rather than production library code.
# ruff: noqa: TRY003, EM101, EM102, PLR2004

from __future__ import annotations

import hashlib
import io
from urllib.error import HTTPError
from urllib.parse import urlsplit


class PipelineDouble:
    def __init__(self, invocation_id: str, run_id: str, run_url: str):
        self.invocation_id = invocation_id
        self.run_id = run_id
        self.run_url = run_url
        self.calls: list[tuple[list[str], object | None]] = []
        self.run_metadata = {
            "id": run_id,
            "html_url": run_url,
            "display_title": invocation_id,
            # Deliberately wrong metadata for the observed-gap probe.
            "workflow_ref": "refs/heads/untrusted.yml",
            "run_attempt": 99,
        }

    def __call__(self, args, data=None, **options):
        if options:
            raise AssertionError(f"unexpected pipeline options: {options}")
        args = list(args)
        self.calls.append((args, data))
        expected_prefix = ["gh", "api", "--hostname", "github.com", "--method"]
        if args[:5] != expected_prefix:
            raise AssertionError(f"unexpected pipeline command: {args}")
        method = args[5]
        endpoint = args[6]
        if method == "POST" and endpoint.endswith("/actions/workflows/coordinated-release.yml/dispatches"):
            if not isinstance(data, dict):
                raise AssertionError("dispatch body was not passed as an object")
            return {}
        if method == "GET" and endpoint.endswith(
            "/actions/workflows/coordinated-release.yml/runs?event=workflow_dispatch&per_page=100"
        ):
            return {"workflow_runs": [dict(self.run_metadata)]}
        raise AssertionError(f"unexpected pipeline endpoint: {endpoint}")


class ArtifactDouble:
    def __init__(
        self,
        artifact: dict,
        archive: bytes,
        *,
        invocation_id: str = "oss-probe-rc-1",
        native=None,
        workflow=None,
    ):
        self.artifact = artifact
        self.archive = archive
        self.invocation_id = invocation_id
        self.native = native or {
            "id": 9001,
            "html_url": "https://github.com/langflow-ai/langflow/actions/runs/9001",
            "repository": {"full_name": "langflow-ai/langflow"},
            "workflow_id": 700,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "display_title": invocation_id,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
        }
        self.workflow = workflow or {"id": 700, "path": ".github/workflows/coordinated-release.yml"}
        self.calls: list[tuple[list[str], bool]] = []

    def __call__(self, args, **options):
        raw = bool(options.get("raw"))
        if set(options) - {"raw"}:
            raise AssertionError(f"unexpected artifact options: {options}")
        args = list(args)
        self.calls.append((args, raw))
        if args == [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "--method",
            "GET",
            "repos/langflow-ai/langflow/actions/runs/9001",
        ]:
            return dict(self.native)
        if args == [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "--method",
            "GET",
            "repos/langflow-ai/langflow/actions/workflows/coordinated-release.yml",
        ]:
            return dict(self.workflow)
        expected = ["gh", "api", "--hostname", "github.com", "--paginate", "--slurp"]
        if args[:6] == expected and args[-1].endswith("/actions/runs/9001/artifacts?per_page=100") and not raw:
            return [{"artifacts": [dict(self.artifact)]}]
        if raw and args == [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "repos/langflow-ai/langflow/actions/artifacts/42/zip",
        ]:
            return self.archive
        raise AssertionError(f"unexpected artifact command: {args}, raw={raw}")


class CosResponse:
    def __init__(self, body: bytes, etag: str):
        self.body, self.headers = body, {"ETag": etag}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class CosHTTPDouble:
    """In-memory S3-compatible endpoint with conditional-write semantics."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.requests: list[dict[str, object]] = []

    @property
    def put_count(self) -> int:
        return sum(request["method"] == "PUT" for request in self.requests)

    def __call__(self, request, *, timeout):
        if timeout != 60:
            raise AssertionError(f"unexpected COS timeout: {timeout}")
        parsed = urlsplit(request.full_url)
        if parsed.hostname != "s3.us-south.cloud-object-storage.appdomain.cloud":
            raise AssertionError(f"unexpected COS host: {parsed.hostname}")
        if not parsed.path.startswith("/fixture/"):
            raise AssertionError(f"unexpected COS path: {parsed.path}")
        method = request.method
        key = parsed.path.removeprefix("/fixture/")
        body = request.data or b""
        headers = {
            "if-none-match": request.get_header("If-none-match"),
            "if-match": request.get_header("If-match"),
            "authorization": request.get_header("Authorization"),
        }
        if headers["authorization"] != "Bearer fixture-token":
            raise AssertionError("COS request did not use the injected token")
        self.requests.append({"method": method, "key": key, "headers": headers, "body": body})
        if method == "GET":
            if key not in self.objects:
                raise HTTPError(request.full_url, 404, "missing fixture", {}, io.BytesIO())
            data, etag = self.objects[key]
            return CosResponse(data, etag)
        if method != "PUT":
            raise AssertionError(f"unexpected COS method: {method}")
        old = self.objects.get(key)
        if headers["if-none-match"] == "*" and old is not None:
            raise HTTPError(request.full_url, 412, "already present", {}, io.BytesIO())
        if headers["if-match"] and (old is None or old[1] != headers["if-match"]):
            raise HTTPError(request.full_url, 412, "etag mismatch", {}, io.BytesIO())
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        self.objects[key] = (body, etag)
        return CosResponse(b"", etag)


class TokenDouble:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, args, **options):
        if options or list(args) != ["ibmcloud", "iam", "oauth-tokens", "--output", "JSON"]:
            raise AssertionError(f"unexpected credential command: {args}, {options}")
        self.calls.append(list(args))
        return {"iam_token": "fixture-token"}
