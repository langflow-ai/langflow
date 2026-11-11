"""Canonical release value encoding."""

import hashlib
import json
import re

from .constants import VERSION


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    )


def identity(version, mode, candidate):
    require(matches(VERSION, version), "version must be canonical X.Y.Z")
    require(mode in {"rc", "official"}, "mode must be rc or official")
    require(
        matches(r"rc\.[1-9][0-9]*", candidate) if mode == "rc" else candidate is None,
        "RC requires rc.N; official requires null candidate",
    )
    return version + ("-" + candidate if mode == "rc" else "")


def platform_key(platform):
    # OCI producers differ in whether ARM's default v8 variant is explicit.
    return "linux/arm64" if platform == "linux/arm64/v8" else platform


def reference(image):
    return f"{image['repository']}@{image['digest']}"
