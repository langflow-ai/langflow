"""Contract v1 input and component-result validation."""

from urllib.parse import urlsplit

from .constants import DEPENDENCIES, DIGEST, PLATFORM, REPOSITORIES, SHA, VERSION
from .contract_values import (
    ContractError,
    digest,
    identity,
    matches,
    platform_key,
    reference,
    require,
)

__all__ = [
    "DEPENDENCIES",
    "DIGEST",
    "PLATFORM",
    "REPOSITORIES",
    "SHA",
    "VERSION",
    "ContractError",
    "digest",
    "identity",
    "matches",
    "platform_key",
    "reference",
    "require",
    "validate_architecture",
    "validate_image",
    "validate_owner",
    "validate_request",
    "validate_result",
    "validate_run",
    "validate_sources",
]


def validate_architecture(architecture):
    require(isinstance(architecture, dict), "architecture policy must be an object")
    platforms = architecture.get("platforms", [])
    require(
        isinstance(platforms, list) and platforms and all(matches(PLATFORM, p) for p in platforms),
        "explicit supported platforms required",
    )
    require(len(set(platforms)) == len(platforms), "duplicate platforms")
    require(
        len({platform_key(p) for p in platforms}) == len(platforms),
        "duplicate platform aliases",
    )
    require(
        bool(architecture.get("approval")),
        "release-engineering architecture approval required",
    )


def validate_owner(request):
    require(
        isinstance(request, dict) and set(request) == {"coordinator_id", "version", "mode", "candidate"},
        "manual request must contain exactly coordinator_id/version/mode/candidate",
    )
    identity(request["version"], request["mode"], request["candidate"])
    require(
        matches(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", request["coordinator_id"]),
        "invalid coordinator identity",
    )


def validate_sources(sources, version):
    require(set(sources) == set(REPOSITORIES), "all four sources must be frozen")
    for component, repository in REPOSITORIES.items():
        source = sources[component]
        require(source.get("repository") == repository, f"wrong repository: {component}")
        require(source.get("branch") == f"release-{version}", "wrong release branch")
        require(matches(SHA, source.get("commit")), "full source SHA required")


def validate_image(image, platforms, *, exact=True):
    require(isinstance(image, dict), "image record required")
    require(
        matches(r"[a-z0-9][a-z0-9.:-]*/[a-z0-9._/-]+", image.get("repository")),
        "qualified image repository required",
    )
    require(
        matches(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", image.get("tag")),
        "invalid image tag",
    )
    require(matches(DIGEST, image.get("digest")), "index digest required")
    actual = image.get("platforms", {})
    require(isinstance(actual, dict) and actual, "platform digests required")
    require(
        all(matches(PLATFORM, p) and matches(DIGEST, d) for p, d in actual.items()),
        "invalid platform digest",
    )
    observed = {platform_key(p) for p in actual}
    expected = {platform_key(p) for p in platforms}
    require(len(observed) == len(actual), "ambiguous platform aliases")
    require(
        observed == expected if exact else expected <= observed,
        "image platform matrix mismatch",
    )


def validate_run(run):
    require(
        isinstance(run, dict) and set(run) == {"provider", "pipeline_id", "id", "url"},
        "complete native run handle required",
    )
    require(run["provider"] in {"github", "sps"}, "unknown run provider")
    require(all(isinstance(run[k], str) and run[k] for k in run), "empty native run field")
    parsed = urlsplit(run["url"])
    require(
        parsed.scheme == "https" and parsed.hostname and not parsed.username,
        "HTTPS run URL required",
    )


def validate_request(request):
    require(isinstance(request, dict), "build request must be an object")
    require(request.get("schema_version") == 1, "unsupported schema")
    component = request.get("component")
    require(component in REPOSITORIES, "unknown component")
    require(
        request.get("release_id") == identity(request["version"], request["mode"], request["candidate"]),
        "release identity mismatch",
    )
    for field in ("coordinator_id", "invocation_id"):
        require(
            matches(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,149}", request.get(field)),
            f"invalid {field}",
        )
    source = request.get("source", {})
    require(
        source.get("repository") == REPOSITORIES[component]
        and source.get("branch") == "release-" + request["version"]
        and matches(SHA, source.get("commit")),
        "invalid frozen source",
    )
    require(matches(SHA, request.get("oss_commit")), "exact OSS commit required")
    validate_architecture({"platforms": request.get("platforms"), "approval": True})
    require(
        set(request.get("dependencies", {})) == set(DEPENDENCIES[component]),
        "wrong dependencies",
    )
    for image in request["dependencies"].values():
        validate_image(image, request["platforms"])
        require(image["tag"] == request["release_id"], "dependency candidate mismatch")
    if component == "operator":
        require(
            set(request.get("installation_images", {})) == set(DEPENDENCIES[component]),
            "installation image mappings required",
        )
        for c, image in request["installation_images"].items():
            validate_image(image, request["platforms"])
            require(
                image["digest"] == request["dependencies"][c]["digest"]
                and image["platforms"] == request["dependencies"][c]["platforms"]
                and image["tag"] == request["release_id"],
                "installation mapping changed image bytes",
            )
        require(
            matches(
                r"[a-z0-9][a-z0-9.:-]*/[a-z0-9._/-]+",
                request.get("installation_repository"),
            ),
            "operator installation repository required",
        )
    validate_image(
        {
            "repository": request.get("destination"),
            "tag": request["release_id"],
            "digest": "sha256:" + "0" * 64,
            "platforms": dict.fromkeys(request["platforms"], "sha256:" + "0" * 64),
        },
        request["platforms"],
    )


def validate_result(result, request, run):
    validate_request(request)
    validate_run(run)
    require(
        run["provider"] == ("github" if request["component"] == "oss" else "sps"),
        "wrong native provider for component",
    )
    require(
        result.get("schema_version") == 1 and result.get("status") == "succeeded",
        "unsuccessful result",
    )
    for field, expected in {
        "request_digest": digest(request),
        "invocation_id": request["invocation_id"],
        "component": request["component"],
        "source_commit": request["source"]["commit"],
        "oss_commit": request["oss_commit"],
        "release_id": request["release_id"],
        "run": run,
        "publication": "staged",
    }.items():
        require(result.get(field) == expected, f"result mismatch: {field}")
    validate_image(result.get("image"), request["platforms"])
    require(
        result["image"]["repository"] == request["destination"] and result["image"]["tag"] == request["release_id"],
        "unexpected image destination/tag",
    )
    packaging = result.get("packaging", {})
    require(
        packaging.get("version") == request["release_id"] and packaging.get("smoke_passed") is True,
        "packaging version/smoke evidence missing",
    )
    if request["component"] == "operator":
        require(
            packaging.get("chart_version") == request["release_id"]
            and packaging.get("app_version") == "v" + request["release_id"],
            "operator version mismatch",
        )
        require(
            packaging.get("component_images") == {k: reference(v) for k, v in request["installation_images"].items()},
            "operator image pins mismatch",
        )
        require(
            packaging.get("operator_repository") == request["installation_repository"],
            "operator chart repository mismatch",
        )
        archive = packaging.get("chart_artifact", {})
        require(
            archive.get("name") == "langflow-operator-" + request["release_id"] + ".tgz"
            and matches(DIGEST, archive.get("digest")),
            "versioned chart archive digest required",
        )
        validate_image(result.get("base_image"), request["platforms"], exact=False)
        require(
            result.get("base_image_reference") == reference(result["base_image"]),
            "Dockerfile base reference mismatch",
        )
