"""Validate later-provider contracts without changing the frozen wave-1 gate."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_ROOT = REPO_ROOT / "design" / "provider-integrations"
WAVE_ONE_PROVIDERS = frozenset({"google", "microsoft", "slack"})


def _read(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"{path}: cannot read contract JSON ({type(exc).__name__})")
        return None


def _inside(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    path = (root / value).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _validate_contract(
    contract: Any,
    *,
    provider: str,
    extension_path: Path,
    manifest_path: Path,
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    label = f"provider contract {provider}"
    required = {
        "schema_version",
        "provider_id",
        "distribution",
        "manifest",
        "sources",
        "transport_limitations",
        "evidence_paths",
        "owner_acceptance",
    }
    if not isinstance(contract, dict) or set(contract) != required or contract.get("schema_version") != 1:
        return [f"{label}: expected a version-1 contract with fields {sorted(required)}"]
    extension = _read(extension_path, errors)
    manifest = _read(manifest_path, errors)
    if not isinstance(extension, dict) or not isinstance(manifest, dict):
        return errors or [f"{label}: extension and manifest must be objects"]
    if contract["provider_id"] != provider or manifest.get("provider_id") != provider:
        errors.append(f"{label}: provider ownership does not match the extension declaration")
    if contract["distribution"] != extension.get("id"):
        errors.append(f"{label}: distribution does not match extension ownership")
    if contract["manifest"] != manifest:
        errors.append(f"{label}: the complete capability/auth-profile manifest differs from the recorded contract")
    sources = contract["sources"]
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label}: official sources are required")
    else:
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"url", "title", "verified_on"}:
                errors.append(f"{label}: each source needs url, title, and verified_on")
                continue
            try:
                if not isinstance(source["url"], str):
                    raise TypeError
                url = urlsplit(source["url"])
                checked = date.fromisoformat(source["verified_on"])
                if (
                    url.scheme != "https"
                    or not url.hostname
                    or url.username
                    or url.password
                    or not isinstance(source["title"], str)
                    or not source["title"].strip()
                    or checked > datetime.now(timezone.utc).date()
                ):
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{label}: source metadata must identify an HTTPS document and a real verification date")
    if not _nonempty_strings(contract["transport_limitations"]):
        errors.append(f"{label}: explicit transport limitations are required")
    evidence = contract["evidence_paths"]
    if not _nonempty_strings(evidence):
        errors.append(f"{label}: repository evidence paths are required")
    else:
        for value in evidence:
            path = _inside(repo_root, value)
            if path is None or not path.exists():
                errors.append(f"{label}: evidence path is missing or outside the repository: {value!r}")
    acceptance = contract["owner_acceptance"]
    if (
        not isinstance(acceptance, dict)
        or acceptance.get("status") not in ("pending", "accepted")
        or not isinstance(acceptance.get("note"), str)
        or not acceptance["note"].strip()
    ):
        errors.append(f"{label}: owner acceptance must explicitly be pending or accepted with a note")
    elif acceptance["status"] == "accepted":
        try:
            if not isinstance(acceptance.get("owner"), str) or not acceptance["owner"].strip():
                raise ValueError
            if date.fromisoformat(acceptance["date"]) > datetime.now(timezone.utc).date():
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}: accepted ownership needs a named owner and a real acceptance date")
    return errors


def validate_contracts(
    manifests: list[tuple[str, Path, Path]],
    *,
    contract_root: Path = DEFAULT_CONTRACT_ROOT,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Require one static, owned contract for each shipped later provider."""
    errors: list[str] = []
    index = _read(contract_root / "index.json", errors)
    if not isinstance(index, dict) or set(index) != {"schema_version", "providers"} or index.get("schema_version") != 1:
        return [*errors, "provider contract index must be a version-1 object with a providers list"]
    entries = index["providers"]
    if not isinstance(entries, list):
        return ["provider contract index providers must be a list"]
    paths: dict[str, Path] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"provider_id", "contract"}:
            errors.append("provider contract index entries need provider_id and contract")
            continue
        provider = entry["provider_id"]
        path = _inside(contract_root, entry["contract"])
        if not isinstance(provider, str) or not provider or provider in WAVE_ONE_PROVIDERS or path is None:
            errors.append("provider contract index contains an invalid provider or contract path")
            continue
        if provider in paths or path in paths.values():
            errors.append(f"provider contract index duplicates provider or path for {provider!r}")
            continue
        paths[provider] = path
    discovered: dict[str, tuple[Path, Path]] = {}
    for provider, extension_path, manifest_path in manifests:
        if provider in WAVE_ONE_PROVIDERS:
            continue
        if provider in discovered:
            errors.append(f"multiple shipped manifests claim later provider {provider!r}")
            continue
        discovered[provider] = extension_path, manifest_path
    errors.extend(
        f"provider contract index has stale entry {provider!r} without a shipped manifest"
        for provider in sorted(paths.keys() - discovered.keys())
    )
    for provider in sorted(discovered):
        if provider not in paths:
            errors.append(f"shipped provider {provider!r} has no indexed provider contract")
            continue
        error_count = len(errors)
        contract = _read(paths[provider], errors)
        if len(errors) == error_count:
            extension_path, manifest_path = discovered[provider]
            errors.extend(
                _validate_contract(
                    contract,
                    provider=provider,
                    extension_path=extension_path,
                    manifest_path=manifest_path,
                    repo_root=repo_root,
                )
            )
    return errors
