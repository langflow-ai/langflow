"""Immutable executable Harness candidates. No database or authoring service dependency.

Version 5 is deliberately distinct from legacy project packages (versions 1-4).
Only entrypoints may be mounted; other definitions are private dependency lookups.
Hashes establish content identity, not publisher trust or permission to execute code.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import version
from types import MappingProxyType
from uuid import UUID

from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import flow_references

MAX_FLOWS = 500
MAX_FLOW_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
SCHEMA_VERSION = 5


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class DefinitionMap(Mapping):
    """Bytes are shared; each lookup returns a detached executable definition."""

    def __init__(self, files: tuple[tuple[str, bytes], ...]):
        self._files = MappingProxyType(dict(files))

    def __getitem__(self, key):
        return json.loads(self._files[key])

    def __iter__(self):
        return iter(self._files)

    def __len__(self):
        return len(self._files)


@dataclass(frozen=True)
class RuntimeCandidate:
    """Validated canonical bytes, independent of mutable graph/run caches."""

    manifest_bytes: bytes
    files: tuple[tuple[str, bytes], ...]

    @property
    def manifest(self) -> dict:
        return json.loads(self.manifest_bytes)

    @property
    def digest(self) -> str:
        return _sha(self.manifest_bytes)

    @property
    def definitions(self) -> DefinitionMap:
        return DefinitionMap(self.files)

    def bind(self, graph) -> None:
        graph.runtime_candidate = self
        graph.frozen_tool_flows = self.definitions

    def inherit(self, parent, child) -> None:
        from copy import deepcopy

        self.bind(child)
        child.execution_principal = parent.execution_principal
        child.persist_messages = parent.persist_messages
        child.end_user_id = parent.end_user_id
        for key in ("no_env_fallback", "request_variables"):
            if key in parent.context:
                child.context[key] = deepcopy(parent.context[key])

    def execution_binding(self, binding):
        """Validate review identity, then validate output contracts on sanitized bytes.

        Original references remain in the graph and run provenance. Scrubbing a
        credential changes an executable hash without changing what was reviewed.
        """
        entry = next((item for item in self.manifest["flows"] if item["id"] == str(binding.flow_id)), None)
        if entry is None or binding.revision != entry["source_revision"]:
            msg = "The binding does not match the candidate's reviewed source."
            raise ValueError(msg)
        return binding.model_copy(update={"revision": flow_revision(self.definitions[str(binding.flow_id)]["data"])})

    def archive(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(_zip_info("manifest.json"), self.manifest_bytes)
            for identity, content in self.files:
                archive.writestr(_zip_info(f"flows/{identity}.json"), content)
        return buffer.getvalue()


def _zip_info(path):
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def candidate_nodes(data):
    pending = list(data.get("nodes", []))
    while pending:
        node = pending.pop()
        yield node
        inner = node.get("data", {}).get("node", {}).get("flow", {}).get("data", {})
        pending.extend(inner.get("nodes", []))


def requirements_for(definitions: list[dict]) -> dict[str, list[str]]:
    """Conservatively describe statically visible resources and suspend paths.

    Dynamic resource/dependency discovery from arbitrary Python is intentionally
    unsupported. Operators still decide whether to trust embedded component code.
    """
    from lfx.base.models.unified_models import get_provider_all_variables

    requirements = {
        key: set()
        for key in ("capabilities", "variables", "connections", "providers", "components", "files", "services")
    }
    for flow in definitions:
        for node in candidate_nodes(flow["data"]):
            inner = node.get("data", {})
            kind = inner.get("type", "")
            requirements["components"].add(kind)
            template = inner.get("node", {}).get("template", {})
            if kind in {"HumanInput", "HumanInputComponent"}:
                requirements["capabilities"].add("durable_approval")
            if kind == "Agent" and (
                template.get("tool_policy", {}).get("value") == "ask"
                or template.get("permission_binding", {}).get("value") not in (None, "", "null", "{}")
            ):
                requirements["capabilities"].add("durable_approval")
            for name, field in template.items():
                if not isinstance(field, dict):
                    continue
                value = field.get("value")
                if isinstance(value, list) and any(
                    isinstance(item, dict) and item.get("approval_actions") for item in value
                ):
                    requirements["capabilities"].add("durable_approval")
                if field.get("load_from_db") and isinstance(value, str) and value:
                    requirements["variables"].add(value)
                if field.get("type") == "connection_ref" and value:
                    requirements["connections"].add(value)
                if field.get("type") == "file":
                    paths = field.get("file_path") or value
                    if paths:
                        requirements["files"].update(paths if isinstance(paths, list) else [paths])
                if (
                    name in {"memory_base_name", "knowledge_base_name", "memory_base", "knowledge_base", "new_kb_name"}
                    and value
                ):
                    requirements["services"].add(f"{name}:{value}")
                if name in {"model", "agent_llm", "embeddings_model", "embedding_model"} and isinstance(value, list):
                    providers = {item["provider"] for item in value if isinstance(item, dict) and item.get("provider")}
                    requirements["providers"].update(providers)
                    for provider in providers:
                        for variable in get_provider_all_variables(provider):
                            field_name = variable.get("component_metadata", {}).get("mapping_field")
                            configured = template.get(field_name, {}).get("value")
                            if variable.get("required") and not configured:
                                requirements["variables"].add(variable["variable_key"])
    return {key: sorted(values) for key, values in requirements.items()}


def _validate_closure(root_id, definitions, entries):
    by_id = {item["id"]: item for item in definitions}
    revisions = {item["id"]: item["source_revision"] for item in entries}
    by_name = {}
    for item in definitions:
        by_name.setdefault(item["name"], []).append(item["id"])
    visited = set()

    def visit(identity, active):
        if identity in active:
            msg = "The candidate contains a recursive flow reference."
            raise ValueError(msg)
        if identity not in by_id:
            msg = "A candidate dependency is missing."
            raise ValueError(msg)
        if identity in visited:
            return
        for reference in flow_references({"nodes": list(candidate_nodes(by_id[identity]["data"]))}):
            target = reference.flow_id
            if not target:
                matches = by_name.get(reference.name, [])
                if len(matches) != 1:
                    msg = "A named candidate dependency is missing or ambiguous."
                    raise ValueError(msg)
                target = matches[0]
            visit(target, active | {identity})
            if reference.revision and reference.revision != revisions[target]:
                msg = "A candidate dependency conflicts with its reviewed revision."
                raise ValueError(msg)
        visited.add(identity)

    visit(root_id, set())
    if visited != set(by_id):
        msg = "Candidate contains definitions outside the entrypoint's dependency closure."
        raise ValueError(msg)
    _validate_reviews(definitions, revisions)


def _validate_reviews(definitions, revisions):
    from lfx.projects.skills import parse_harness_skills
    from lfx.projects.tool_packs import ToolPackToolBinding

    for definition in definitions:
        nodes = list(candidate_nodes(definition["data"]))
        packs = {}
        for node in nodes:
            raw = (node.get("data", {}).get("_harness_tool") or {}).get("tool_pack")
            if not raw:
                continue
            binding = ToolPackToolBinding.model_validate(raw)
            binding.dependency_snapshots()
            for source in (binding.tool, *binding.tool.dependencies):
                if revisions.get(str(source.flow_id)) != source.revision:
                    msg = "A Tool Pack dependency is missing or conflicts with its reviewed revision."
                    raise ValueError(msg)
            previous = packs.setdefault(binding.reference.project_id, binding.reference)
            if previous != binding.reference:
                msg = "A candidate cannot contain conflicting reviews of one Tool Pack."
                raise ValueError(msg)
        for node in nodes:
            inner = node.get("data", {})
            if inner.get("type") != "Agent":
                continue
            skills = parse_harness_skills(
                inner.get("node", {}).get("template", {}).get("skill_bindings", {}).get("value") or ""
            )
            for pack in skills.packs:
                for skill in pack.skills:
                    for reference in skill.tool_packs:
                        if packs.get(reference.project_id) != reference:
                            msg = "A Skill Pack requires a reviewed Tool Pack that is missing from this candidate."
                            raise ValueError(msg)


def build_candidate(
    root_id: str,
    definitions: list[dict],
    *,
    source_revisions: dict[str, str] | None = None,
    required_variables: tuple[str, ...] = (),
    packages: tuple[str, ...] = (),
) -> RuntimeCandidate:
    """Materialize already-authorized, sanitized definitions into deterministic bytes.

    The backend validates original versions before scrubbing; source_revisions
    links them to the executable hashes. This primitive performs no authorization.
    """
    if not 0 < len(definitions) <= MAX_FLOWS:
        msg = "A candidate must contain between 1 and 500 flows."
        raise ValueError(msg)
    if len({item["id"] for item in definitions}) != len(definitions):
        msg = "Duplicate candidate flow identity."
        raise ValueError(msg)
    files = []
    entries = []
    total = 0
    for item in sorted(definitions, key=lambda item: item["id"]):
        identity = item["id"]
        if str(UUID(identity)) != identity:
            msg = "Candidate flow IDs must be canonical UUIDs."
            raise ValueError(msg)
        content = canonical(item)
        total += len(content)
        if len(content) > MAX_FLOW_BYTES or total > MAX_EXPANDED_BYTES:
            msg = "Candidate exceeds the executable size limit."
            raise ValueError(msg)
        files.append((identity, content))
        entries.append(
            {
                "id": identity,
                "path": f"flows/{identity}.json",
                "size": len(content),
                "sha256": _sha(content),
                "source_revision": (source_revisions or {}).get(identity, flow_revision(item["data"])),
            }
        )
    _validate_closure(root_id, definitions, entries)
    requirements = requirements_for(definitions)
    requirements["variables"] = sorted(set(requirements["variables"]) | set(required_variables))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "harness-candidate",
        "runtime": {"lfx": version("lfx"), "packages": sorted(set(packages))},
        "entrypoints": [root_id],
        "flows": entries,
        "requirements": requirements,
    }
    manifest_bytes = canonical(manifest)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        msg = "Candidate manifest exceeds the size limit."
        raise ValueError(msg)
    return RuntimeCandidate(manifest_bytes, tuple(files))


def _decode(content):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                msg = "Duplicate JSON member in candidate."
                raise ValueError(msg)
            value[key] = item
        return value

    return json.loads(content, object_pairs_hook=unique)


def read_candidate(content: bytes, *, expected_digest: str | None = None) -> RuntimeCandidate:
    """Verify exact members, bounded expansion, closure and identity before loading code."""
    if len(content) > MAX_EXPANDED_BYTES + MAX_MANIFEST_BYTES:
        msg = "Candidate archive exceeds the size limit."
        raise ValueError(msg)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > MAX_FLOWS + 1:
                msg = "Duplicate or excessive candidate archive members."
                raise ValueError(msg)
            with archive.open("manifest.json") as member:
                manifest_bytes = member.read(MAX_MANIFEST_BYTES + 1)
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                msg = "Candidate manifest exceeds the size limit."
                raise ValueError(msg)
            manifest = _decode(manifest_bytes)
            if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != "harness-candidate":
                msg = "Unsupported candidate manifest version or kind."
                raise ValueError(msg)
            if set(manifest) != {"schema_version", "kind", "runtime", "entrypoints", "flows", "requirements"}:
                msg = "Unknown candidate manifest fields."
                raise ValueError(msg)
            canonical_manifest = canonical(manifest)
            if expected_digest and _sha(canonical_manifest) != expected_digest:
                msg = "Candidate digest does not match the selected candidate."
                raise ValueError(msg)
            entries = manifest["flows"]
            if not 0 < len(entries) <= MAX_FLOWS or len(manifest["entrypoints"]) != 1:
                msg = "Invalid candidate entrypoints or flow count."
                raise ValueError(msg)
            expected_paths = {"manifest.json"}
            files = []
            total = 0
            for entry in entries:
                identity = entry["id"]
                if str(UUID(identity)) != identity or entry["path"] != f"flows/{identity}.json":
                    msg = "Invalid candidate member path."
                    raise ValueError(msg)
                if set(entry) != {"id", "path", "size", "sha256", "source_revision"}:
                    msg = "Unknown candidate flow metadata."
                    raise ValueError(msg)
                if entry["path"] in expected_paths:
                    msg = "Duplicate candidate flow identity."
                    raise ValueError(msg)
                expected_paths.add(entry["path"])
                size = entry["size"]
                if type(size) is not int or not 0 < size <= MAX_FLOW_BYTES:
                    msg = "Invalid candidate member size."
                    raise ValueError(msg)
                total += size
                if total > MAX_EXPANDED_BYTES:
                    msg = "Candidate exceeds expanded size limit."
                    raise ValueError(msg)
                with archive.open(entry["path"]) as member:
                    raw = member.read(size + 1)
                if len(raw) != size or _sha(raw) != entry["sha256"]:
                    msg = "Candidate member integrity check failed."
                    raise ValueError(msg)
                definition = _decode(raw)
                if definition["id"] != identity:
                    msg = "Candidate member identity mismatch."
                    raise ValueError(msg)
                files.append((identity, raw))
            if set(names) != expected_paths:
                msg = "Unexpected candidate archive members."
                raise ValueError(msg)
            definitions = [json.loads(raw) for _, raw in files]
            _validate_closure(manifest["entrypoints"][0], definitions, entries)
            required = requirements_for(definitions)
            if set(manifest["requirements"]) != set(required) or any(
                not isinstance(manifest["requirements"][key], list)
                or not set(values) <= set(manifest["requirements"][key])
                for key, values in required.items()
            ):
                msg = "Candidate omits executable resource requirements."
                raise ValueError(msg)
            return RuntimeCandidate(canonical_manifest, tuple(files))
    except (
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
    ) as exc:
        msg = "Unreadable Harness candidate."
        raise ValueError(msg) from exc
