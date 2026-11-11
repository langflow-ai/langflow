"""OSS Contract v1 dispatch/result helpers and CLI."""

# ruff: noqa: TRY003, EM101

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .contract import DIGEST, ContractError, digest, identity, platform_key, require
from .contract import validate_request as contract_validate_request
from .contract import validate_result as contract_validate_result
from .execution import reserve, smoke
from .packaging import materialize_versions, package_version, update_frozen_uv_lock


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    """Apply the canonical Contract v1 validator plus OSS-only guards."""
    contract_validate_request(request)
    require(request.get("component") == "oss", "OSS workflow accepts only component=oss")
    require(request["oss_commit"] == request["source"]["commit"], "OSS source and oss_commit differ")
    return request


def parse_envelope(raw: str, invocation_id: str) -> tuple[dict[str, Any], str]:
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError("release_request is not valid JSON") from exc
    require(
        isinstance(envelope, dict) and set(envelope) == {"request", "request_digest"}, "invalid release envelope fields"
    )
    request = validate_request(envelope["request"])
    expected = digest(request)
    require(envelope["request_digest"] == expected, "request_digest mismatch")
    require(request["invocation_id"] == invocation_id, "invocation_id mismatch")
    return request, expected


def validate_provenance(labels: dict[str, str], source_commit: str, release: str, request_digest: str) -> None:
    expected = {
        "org.opencontainers.image.revision": source_commit,
        "org.opencontainers.image.version": release,
        "langflow.org/release-request": request_digest,
    }
    require(
        isinstance(labels, dict) and all(labels.get(key) == value for key, value in expected.items()),
        "required provenance labels missing or mismatched",
    )


def build_result(
    request: dict[str, Any],
    request_digest: str,
    *,
    run_id: str,
    run_url: str,
    index_digest: str,
    platform_digests: dict[str, str],
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble an immutable OSS result after registry verification."""
    validate_request(request)
    require(request_digest == digest(request), "request digest mismatch")
    require(run_id and run_url.startswith("https://"), "native run identity required")
    require(re.fullmatch(DIGEST, index_digest) is not None, "image index digest required")
    expected_platforms = {platform_key(item) for item in request["platforms"]}
    require({platform_key(item) for item in platform_digests} == expected_platforms, "platform digest matrix mismatch")
    require(all(re.fullmatch(DIGEST, value) for value in platform_digests.values()), "invalid platform digest")
    if labels:
        validate_provenance(labels, request["source"]["commit"], request["release_id"], request_digest)
    run = {"provider": "github", "pipeline_id": "coordinated-release.yml", "id": run_id, "url": run_url}
    result = {
        "schema_version": 1,
        "request_digest": request_digest,
        "invocation_id": request["invocation_id"],
        "component": "oss",
        "source_commit": request["source"]["commit"],
        "oss_commit": request["oss_commit"],
        "release_id": request["release_id"],
        "status": "succeeded",
        "run": run,
        "image": {
            "repository": request["destination"],
            "tag": request["release_id"],
            "digest": index_digest,
            "platforms": platform_digests,
        },
        "publication": "staged",
        "packaging": {
            "version": request["release_id"],
            "python_version": package_version(request["version"], request["mode"], request.get("candidate")),
            "smoke_passed": True,
        },
    }
    if labels:
        result["provenance"] = {"labels": labels}
    contract_validate_result(result, request, run)
    return result


validate_result = contract_validate_result
canonical_digest = digest


def _command_validate(args: argparse.Namespace) -> None:
    request, request_digest = parse_envelope(Path(args.request_file).read_text(), args.invocation_id)
    print(json.dumps({"request": request, "request_digest": request_digest}, separators=(",", ":")))


def _command_version(args: argparse.Namespace) -> None:
    request = validate_request(json.loads(Path(args.request_file).read_text()))
    print(
        json.dumps(
            {
                "release_id": identity(request["version"], request["mode"], request.get("candidate")),
                "python_version": package_version(request["version"], request["mode"], request.get("candidate")),
            },
            separators=(",", ":"),
        )
    )


def _command_materialize(args: argparse.Namespace) -> None:
    materialize_versions(args.source, args.release_id, args.python_version)


def _command_lock(args: argparse.Namespace) -> None:
    update_frozen_uv_lock(args.source, args.python_version)


def _command_result(args: argparse.Namespace) -> None:
    request = validate_request(json.loads(Path(args.request_file).read_text()))
    request_digest = digest(request)
    if args.image:
        image_document = json.loads(Path(args.image).read_text())
        image = image_document.get("image", image_document)
        require(image.get("repository") == request["destination"], "image repository differs from request")
        require(image.get("tag") == request["release_id"], "image tag differs from request")
        index_digest, platform_digests = image["digest"], image["platforms"]
        labels = image_document.get("labels") or image_document.get("provenance", {}).get("labels")
    else:
        require(args.index_digest and args.platform_digests, "image record or digest/platform files required")
        index_digest = args.index_digest
        platform_digests = json.loads(Path(args.platform_digests).read_text())
        labels = json.loads(Path(args.labels).read_text()) if args.labels else None
    result = build_result(
        request,
        request_digest,
        run_id=args.run_id,
        run_url=args.run_url,
        index_digest=index_digest,
        platform_digests=platform_digests,
        labels=labels,
    )
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--request-file", required=True)
    validate.add_argument("--invocation-id", required=True)
    validate.set_defaults(func=_command_validate)
    version = commands.add_parser("version")
    version.add_argument("--request-file", required=True)
    version.set_defaults(func=_command_version)
    materialize = commands.add_parser("materialize")
    materialize.add_argument("--source", required=True)
    materialize.add_argument("--release-id", required=True)
    materialize.add_argument("--python-version", required=True)
    materialize.set_defaults(func=_command_materialize)
    lock = commands.add_parser("lock")
    lock.add_argument("--source", required=True)
    lock.add_argument("--python-version", required=True)
    lock.set_defaults(func=_command_lock)
    result = commands.add_parser("result")
    result.add_argument("--request-file", required=True)
    result.add_argument("--run-id", required=True)
    result.add_argument("--run-url", required=True)
    result.add_argument("--index-digest")
    result.add_argument("--platform-digests")
    result.add_argument("--labels")
    result.add_argument("--image")
    result.add_argument("--output", required=True)
    result.set_defaults(func=_command_result)
    reserve_parser = commands.add_parser("reserve")
    reserve_parser.add_argument("--command", required=True)
    reserve_parser.add_argument("--allowlist", required=True)
    reserve_parser.add_argument("--destination", required=True)
    reserve_parser.add_argument("--request-file", required=True)
    reserve_parser.add_argument("--run-file", required=True)
    reserve_parser.set_defaults(
        func=lambda args: reserve(
            args.command,
            request_file=args.request_file,
            run_file=args.run_file,
            destination=args.destination,
            allowlist=args.allowlist,
        )
    )
    smoke_parser = commands.add_parser("smoke")
    smoke_parser.add_argument("--image")
    smoke_parser.add_argument("--image-record")
    smoke_parser.add_argument("--platforms")
    smoke_parser.add_argument("--python-version", required=True)
    smoke_parser.set_defaults(
        func=lambda args: smoke(args.image, args.image_record, args.platforms, args.python_version)
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        args.func(args)
    except (ContractError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"coordinated release rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
