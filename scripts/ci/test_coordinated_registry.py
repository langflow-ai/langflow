"""Challenge raw registry provenance with content-addressed local fixtures."""

import copy
import hashlib
import json

import pytest

from scripts.ci.coordinated_release.contract import ContractError, digest
from scripts.ci.coordinated_release.registry import inspect_image

pytest_plugins = ("scripts.ci.test_coordinated_transport",)


def registry_fixture(
    request, *, labels=None, config_architecture="amd64", descriptor_architecture="amd64", variant=None
):
    """Build real hash-linked index/manifest/config bytes without a registry."""
    objects = {}

    def put(kind, value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
        objects[kind, request["destination"] + "@" + checksum] = raw
        return checksum

    config = {
        "os": "linux",
        "architecture": config_architecture,
        "config": {
            "Labels": labels
            if labels is not None
            else {
                "org.opencontainers.image.revision": request["source"]["commit"],
                "org.opencontainers.image.version": request["release_id"],
                "langflow.org/release-request": digest(request),
            }
        },
    }
    config_digest = put("blob", config)
    manifest_digest = put(
        "manifest",
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"digest": config_digest},
            "layers": [],
        },
    )
    platform = {"os": "linux", "architecture": descriptor_architecture}
    if variant:
        platform["variant"] = variant
    index_digest = put(
        "manifest",
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {"digest": manifest_digest, "platform": platform},
                {"digest": "sha256:" + "f" * 64, "platform": {"os": "unknown", "architecture": "unknown"}},
            ],
        },
    )
    objects["manifest", request["destination"] + ":" + request["release_id"]] = objects[
        "manifest", request["destination"] + "@" + index_digest
    ]
    return index_digest, manifest_digest, config_digest, objects


def test_verifies_actual_bytes_labels_platform_and_tag(evidence):
    request = evidence[0]["request"]
    index, manifest, _, objects = registry_fixture(request)
    result = inspect_image(request, index, lambda kind, reference: objects[kind, reference])
    assert result == {
        "repository": request["destination"],
        "tag": request["release_id"],
        "digest": index,
        "platforms": {"linux/amd64": manifest},
    }


@pytest.mark.parametrize("object_kind", ["index", "manifest", "config", "tag"])
def test_changed_bytes_never_produce_evidence(evidence, object_kind):
    request = evidence[0]["request"]
    index, manifest, config, objects = registry_fixture(request)
    suffix = {
        "index": "@" + index,
        "manifest": "@" + manifest,
        "config": "@" + config,
        "tag": ":" + request["release_id"],
    }[object_kind]
    key = ("blob" if object_kind == "config" else "manifest", request["destination"] + suffix)
    objects[key] += b" "
    with pytest.raises(ContractError, match="bytes do not match"):
        inspect_image(request, index, lambda kind, reference: objects[kind, reference])


@pytest.mark.parametrize(
    "label", ["org.opencontainers.image.revision", "org.opencontainers.image.version", "langflow.org/release-request"]
)
def test_valid_hash_chain_with_wrong_provenance_fails(evidence, label):
    request = evidence[0]["request"]
    labels = {
        "org.opencontainers.image.revision": request["source"]["commit"],
        "org.opencontainers.image.version": request["release_id"],
        "langflow.org/release-request": digest(request),
    }
    labels[label] = "incorrect"
    index, _, _, objects = registry_fixture(request, labels=labels)
    with pytest.raises(ContractError, match="provenance labels"):
        inspect_image(request, index, lambda kind, reference: objects[kind, reference])


def test_valid_hash_chain_with_mismatched_config_cpu_fails(evidence):
    request = evidence[0]["request"]
    index, _, _, objects = registry_fixture(request, config_architecture="arm64")
    with pytest.raises(ContractError, match="config platform"):
        inspect_image(request, index, lambda kind, reference: objects[kind, reference])


def test_preserves_actual_arm64_variant_while_accepting_alias(evidence):
    request = copy.deepcopy(evidence[0]["request"])
    request["platforms"] = ["linux/arm64"]
    index, manifest, _, objects = registry_fixture(
        request, config_architecture="arm64", descriptor_architecture="arm64", variant="v8"
    )
    result = inspect_image(request, index, lambda kind, reference: objects[kind, reference])
    assert result["platforms"] == {"linux/arm64/v8": manifest}


def test_extra_runtime_cpu_cannot_satisfy_different_requested_matrix(evidence):
    request = copy.deepcopy(evidence[0]["request"])
    request["platforms"] = ["linux/arm64"]
    index, _, _, objects = registry_fixture(request)
    with pytest.raises(ContractError, match="platform matrix"):
        inspect_image(request, index, lambda kind, reference: objects[kind, reference])
