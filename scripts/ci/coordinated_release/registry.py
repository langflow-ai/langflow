"""Verify staged registry bytes against the frozen OSS release request."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from .contract import DIGEST, digest, platform_key, require, validate_request

INDEX_TYPES = {"application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"}
MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"}
SCHEMA_VERSION = 2


def fetch_registry(kind, reference):
    """Use the worker's pinned crane installation and existing registry login."""
    require(kind in {"manifest", "blob"}, "invalid registry object type")
    response = subprocess.run(  # noqa: S603 - fixed command, validated references, no shell.
        ["crane", kind, reference],  # noqa: S607 - worker provisioning supplies the pinned executable on PATH.
        capture_output=True,
        check=False,
        timeout=120,
    )
    require(response.returncode == 0, "registry read failed; no component result produced")
    return response.stdout


def _verified_json(data, expected):
    require(isinstance(expected, str) and re.fullmatch(DIGEST, expected), "invalid registry digest")
    require("sha256:" + hashlib.sha256(data).hexdigest() == expected, "registry bytes do not match digest")
    value = json.loads(data)
    require(isinstance(value, dict), "registry object must be JSON object")
    return value


def _platform(value):
    name = str(value.get("os", "")) + "/" + str(value.get("architecture", ""))
    return name + ("/" + value["variant"] if value.get("variant") else "")


def inspect_image(request, expected_index_digest, fetch=fetch_registry):
    """Verify every runtime descriptor, config, provenance label and release tag."""
    validate_request(request)
    require(
        isinstance(expected_index_digest, str) and re.fullmatch(DIGEST, expected_index_digest), "invalid index digest"
    )
    repository = request["destination"]
    index = _verified_json(fetch("manifest", repository + "@" + expected_index_digest), expected_index_digest)
    require(
        index.get("mediaType") in INDEX_TYPES and index.get("schemaVersion") == SCHEMA_VERSION,
        "multi-platform index required",
    )
    descriptors = index.get("manifests")
    require(isinstance(descriptors, list) and descriptors, "runtime platform descriptors required")
    platforms = {}
    expected_labels = {
        "org.opencontainers.image.revision": request["source"]["commit"],
        "org.opencontainers.image.version": request["release_id"],
        "langflow.org/release-request": digest(request),
    }
    for descriptor in descriptors:
        require(
            isinstance(descriptor, dict) and isinstance(descriptor.get("platform"), dict),
            "platform descriptor required",
        )
        platform = _platform(descriptor["platform"])
        # BuildKit attestations describe metadata, not runnable platforms.
        if platform == "unknown/unknown":
            continue
        require(platform not in platforms, "duplicate runtime platform")
        manifest_digest = descriptor.get("digest")
        require(isinstance(manifest_digest, str) and re.fullmatch(DIGEST, manifest_digest), "invalid manifest digest")
        manifest = _verified_json(fetch("manifest", repository + "@" + manifest_digest), manifest_digest)
        require(
            manifest.get("mediaType") in MANIFEST_TYPES and manifest.get("schemaVersion") == SCHEMA_VERSION,
            "runtime manifest required",
        )
        config_digest = manifest.get("config", {}).get("digest")
        require(isinstance(config_digest, str) and re.fullmatch(DIGEST, config_digest), "invalid config digest")
        config = _verified_json(fetch("blob", repository + "@" + config_digest), config_digest)
        require(platform_key(_platform(config)) == platform_key(platform), "config platform differs from index")
        labels = config.get("config", {}).get("Labels", {})
        require(
            isinstance(labels, dict) and all(labels.get(k) == v for k, v in expected_labels.items()),
            "image provenance labels mismatch",
        )
        platforms[platform] = manifest_digest
    observed = {platform_key(p) for p in platforms}
    require(len(observed) == len(platforms), "ambiguous platform aliases")
    require(observed == {platform_key(p) for p in request["platforms"]}, "runtime platform matrix mismatch")
    _verified_json(fetch("manifest", repository + ":" + request["release_id"]), expected_index_digest)
    return {
        "repository": repository,
        "tag": request["release_id"],
        "digest": expected_index_digest,
        "platforms": platforms,
    }


def main(argv=None):
    """Write the verified Contract v1 image record for the result builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--index-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = inspect_image(json.loads(args.request_file.read_text()), args.index_digest)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
