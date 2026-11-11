"""Bounded execution helpers for the coordinated OSS workflow."""

# ruff: noqa: S603, S607

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from .contract import DIGEST, SHA, require, validate_request, validate_run


def verify_checkout(path: str | Path, expected_commit: str) -> None:
    require(re.fullmatch(SHA, expected_commit) is not None, "invalid expected checkout SHA")
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=120
    )
    actual = completed.stdout.strip().lower()
    require(actual == expected_commit, f"source checkout mismatch: {actual} != {expected_commit}")


def validate_staging_destination(destination: str, allowlist: str) -> None:
    entries = tuple(item.strip().rstrip("/") for item in allowlist.split(",") if item.strip())
    require(entries and destination in entries, "staging destination is not allowlisted")


def reserve(command_json: str, *, request_file: str, run_file: str, destination: str, allowlist: str) -> None:
    command = json.loads(command_json)
    require(
        isinstance(command, list) and command and all(isinstance(item, str) and item for item in command),
        "reservation adapter must be a nonempty argv array",
    )
    validate_staging_destination(destination, allowlist)
    request = json.loads(Path(request_file).read_text())
    run = json.loads(Path(run_file).read_text())
    validate_request(request)
    require(request.get("component") == "oss", "reservation request is not for OSS")
    require(request.get("oss_commit") == request["source"]["commit"], "OSS source and oss_commit differ")
    require(request.get("destination") == destination, "reservation destination differs from request")
    validate_run(run)
    run_id = run.get("id")
    require(run.get("provider") == "github", "reservation run provider mismatch")
    require(run.get("pipeline_id") == "coordinated-release.yml", "reservation pipeline identity mismatch")
    require(isinstance(run_id, str) and re.fullmatch(r"[1-9][0-9]*", run_id), "reservation run id must be numeric")
    require(
        run.get("url") == f"https://github.com/langflow-ai/langflow/actions/runs/{run_id}",
        "reservation run URL identity mismatch",
    )
    completed = subprocess.run(
        command,
        input=json.dumps({"request": request, "run": run}),
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    require(completed.stdout.strip().lower() == "true", "reservation adapter did not confirm unique reservation")


def smoke(image: str | None, image_record: str | None, platforms_file: str | None, python_version: str) -> None:
    require(bool(image) ^ bool(image_record), "exactly one image or image-record is required")
    record = json.loads(Path(image_record).read_text()) if image_record else None
    if record:
        record = record.get("image", record)
        require(isinstance(record, dict), "image record must be an object")
        require(isinstance(record.get("repository"), str) and record["repository"], "image repository required")
        require(isinstance(record.get("tag"), str) and record["tag"], "image tag required")
        platform_digests = record.get("platforms")
        require(
            isinstance(platform_digests, dict)
            and platform_digests
            and all(
                isinstance(platform, str) and re.fullmatch(DIGEST, digest)
                for platform, digest in platform_digests.items()
            ),
            "immutable platform digests required",
        )
        platforms = list(platform_digests)
    else:
        require(platforms_file is not None, "platforms file required")
        require(re.search(r"@sha256:[0-9a-f]{64}$", image or "") is not None, "immutable image digest required")
        platforms = json.loads(Path(platforms_file).read_text())
    require(isinstance(platforms, list) and platforms, "smoke platform list required")
    command = (
        "import importlib.metadata as m; "
        f"assert m.version('langflow') == {python_version!r}; "
        f"assert m.version('langflow-base') == {python_version!r}; "
        "import langflow, pathlib; "
        "root=pathlib.Path(langflow.__file__).parent; "
        f"marker=next(root.rglob('coordinated-release-version.txt')); "
        f"assert marker.read_text().strip() == {record.get('tag') if record else python_version!r}"
    )
    for platform in platforms:
        reference = image if not record else record["repository"] + "@" + record["platforms"][platform]
        subprocess.run(["docker", "pull", "--platform", platform, reference], check=True, timeout=180)
        suffix = uuid4().hex[:12]
        metadata_name = "lf-coordinated-smoke-metadata-" + suffix
        help_name = "lf-coordinated-smoke-help-" + suffix
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    metadata_name,
                    "--rm",
                    "--platform",
                    platform,
                    "--entrypoint",
                    "python",
                    reference,
                    "-c",
                    command,
                ],
                check=True,
                timeout=180,
            )
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    help_name,
                    "--rm",
                    "--platform",
                    platform,
                    "--entrypoint",
                    "langflow",
                    reference,
                    "--help",
                ],
                check=True,
                timeout=120,
            )
        finally:
            for name in (metadata_name, help_name):
                subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True, timeout=30)
