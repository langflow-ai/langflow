"""Export installed component contracts in an isolated, network-disabled process."""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib
import inspect
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Keep refusal evidence even when imported component code catches the exception.
_refused_calls: list[str] = []
# Registry imports set the reviewed OpenTelemetry semantic-convention flag.
_METADATA_ENVIRONMENT = frozenset(
    {
        "PATH",
        "HOME",
        "LANGFLOW_CONFIG_DIR",
        "DO_NOT_TRACK",
        "LITELLM_LOCAL_MODEL_COST_MAP",
        "OTEL_SEMCONV_STABILITY_OPT_IN",
    }
)


class RegistrySnapshotError(RuntimeError):
    """An installed registry could not be exported completely."""


def _is_trusted_local_probe(arguments: tuple, program: str, options: tuple[str, ...]) -> bool:
    """Match the actual executable selected by this subprocess's environment."""
    try:
        executable, argv, _cwd, environment = arguments
    except (TypeError, ValueError):
        return False
    trusted = Path(f"/usr/bin/{program}").resolve()
    allowed = {program, str(trusted)}
    if not trusted.is_file() or not isinstance(executable, str) or executable not in allowed:
        return False
    if (
        not isinstance(argv, (list, tuple))
        or not argv
        or not isinstance(argv[0], str)
        or argv[0] not in allowed
        or tuple(argv[1:]) != options
    ):
        return False
    environment = os.environ if environment is None else environment
    if not isinstance(environment, Mapping):
        return False
    if environment.get("PATH") != os.defpath:
        return False
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            return False
        # GitPython and platform force C locale for their metadata parsers.
        if name in {"LANGUAGE", "LC_ALL"} and value == "C":
            continue
        if name == "PATH":
            continue
        if name not in _METADATA_ENVIRONMENT or value != os.environ.get(name):
            return False
    resolved = shutil.which(executable, path=os.defpath)
    return resolved is not None and Path(resolved).resolve() == trusted


def _is_interpreter_file_probe(arguments: tuple) -> bool:
    """Allow croniter's platform.architecture probe of this interpreter only."""
    try:
        _executable, argv, _cwd, _environment = arguments
        if not isinstance(argv, (list, tuple)):
            return False
        _program, _option, target = argv
    except (TypeError, ValueError):
        return False
    return (
        isinstance(target, str)
        and Path(target).is_absolute()
        and os.path.realpath(target) == os.path.realpath(sys.executable)
        and _is_trusted_local_probe(arguments, "file", ("-b", target))
    )


def _refuse_network(event: str, _args: tuple) -> None:
    if event == "subprocess.Popen":
        try:
            allowed = _is_interpreter_file_probe(_args) or _is_trusted_local_probe(_args, "git", ("version",))
        except Exception:  # noqa: BLE001 -- malformed probe validation must retain refusal evidence
            allowed = False
        if allowed:
            return
    if event in {
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyaddr",
        "socket.sendto",
        "socket.sendmsg",
        "socket.getnameinfo",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.exec",
        "os.spawn",
        "os.fork",
        "os.forkpty",
        "os.startfile",
        "os.startfile/2",
        "pty.spawn",
    }:
        _refused_calls.append(event)
        msg = "component registry export does not allow network access or subprocesses"
        raise RegistrySnapshotError(msg)


def normalize_name(value: str) -> str:
    import re

    return re.sub(r"[-_.]+", "-", value).lower()


def _installed() -> dict[str, str]:
    return {
        normalize_name(dist.metadata["Name"]): dist.version
        for dist in metadata.distributions()
        if dist.metadata.get("Name") and (dist.metadata["Name"].lower().startswith(("lfx", "langflow")))
    }


def project_provider_contracts(all_types, descriptors, configure, distributions, core_distribution):
    """Project real model fields through the runtime's provider configuration helper."""
    language_model = next(
        (entry for entries in all_types.values() for key, entry in entries.items() if key == "LanguageModelComponent"),
        None,
    )
    if language_model is None:
        if any(descriptor.origin for descriptor in descriptors.values()):
            msg = "registered providers have no LanguageModel component contract"
            raise RegistrySnapshotError(msg)
        return {}, {}
    mapped_fields = {
        variable.get("component_metadata", {}).get("mapping_field")
        for descriptor in descriptors.values()
        for variable in descriptor.metadata.get("variables", ())
    }
    contracts, packages = {}, {}
    for descriptor in descriptors.values():
        origin = descriptor.origin
        package = normalize_name(origin.distribution) if origin and origin.distribution else core_distribution
        if package not in distributions:
            msg = f"{descriptor.name} has no installed provider distribution provenance"
            raise RegistrySnapshotError(msg)
        active_fields = {
            variable.get("component_metadata", {}).get("mapping_field")
            for variable in descriptor.metadata.get("variables", ())
        }
        template = configure(copy.deepcopy(language_model["template"]), descriptor.name)
        # Only declared model fields are saved in a node. Manifest mappings do
        # not invent additional component inputs.
        template = {
            key: field
            for key, field in template.items()
            if key != "_type" and (key not in mapped_fields or key in active_fields)
        }
        for name in (descriptor.name, *descriptor.aliases):
            key = f"provider:{name}:LanguageModelComponent"
            contracts[key] = {"template": template, "outputs": copy.deepcopy(language_model["outputs"])}
            packages[key] = package
    return contracts, packages


def collect_snapshot() -> dict[str, Any]:
    """Use the installed runtime's own registry and reject degraded bundle discovery."""
    distributions = _installed()
    namespace = "lfx" if "lfx" in distributions else "langflow"
    components = importlib.import_module(f"{namespace}.interface.components")
    read_index = getattr(components, "_read_component_index", None)
    if read_index is None:
        msg = "the published runtime cannot expose its component index"
        raise RegistrySnapshotError(msg)
    blob = read_index(None)
    if not blob or not blob.get("entries"):
        msg = "the installed component index is unavailable or empty"
        raise RegistrySnapshotError(msg)
    all_types: dict[str, dict] = {}
    packages = {}
    core_distribution = "lfx" if namespace == "lfx" else "langflow-base"
    for category, entries in blob["entries"]:
        all_types.setdefault(category, {}).update(entries)
        packages.update(dict.fromkeys(entries, core_distribution))

    bundle_entry_points = [
        ep for group in ("langflow.extensions", "lfx.bundles") for ep in metadata.entry_points().select(group=group)
    ]
    import_extensions = getattr(components, "import_extension_components", None)
    if bundle_entry_points and import_extensions is None:
        msg = "installed bundles cannot be completely discovered by this published runtime"
        raise RegistrySnapshotError(msg)
    if import_extensions is not None:
        captured = []
        emit = getattr(components, "_emit_extension_diagnostics", None)
        if emit is None and bundle_entry_points:
            msg = "the runtime cannot expose bundle discovery failures"
            raise RegistrySnapshotError(msg)

        def capture(results):
            captured.extend(results)
            if emit is not None:
                emit(results)

        if emit is not None:
            components._emit_extension_diagnostics = capture  # noqa: SLF001
        try:
            parameters = inspect.signature(import_extensions).parameters
            if "components_path" in parameters:
                pending = import_extensions(components_path=[])
            elif "settings_service" in parameters:
                # Published runtimes before the isolated-loader API read only
                # this path list. Do not start a settings or database service.
                pending = import_extensions(SimpleNamespace(settings=SimpleNamespace(components_path=[])))
            else:
                msg = "the published extension loader has an unsupported discovery signature"
                raise RegistrySnapshotError(msg)
            extensions = asyncio.run(pending)
        finally:
            if emit is not None:
                components._emit_extension_diagnostics = emit  # noqa: SLF001
        errors = [
            f"{result.bundle or '<unknown>'}/{error.code}: {getattr(error, 'message', '')}"
            for result in captured
            for error in result.errors
        ]
        if errors:
            msg = "incomplete bundle discovery " + ", ".join(sorted(errors))
            raise RegistrySnapshotError(msg)
        for result in captured:
            if not result.components:
                continue
            package = normalize_name(result.distribution) if result.distribution else None
            if package not in distributions:
                candidate = normalize_name(f"lfx-{result.bundle}")
                package = candidate if candidate in distributions else "lfx-bundles"
            if package not in distributions:
                msg = f"{result.bundle} has no installed distribution provenance"
                raise RegistrySnapshotError(msg)
            templates = extensions.get(result.bundle, {})
            expected = {loaded.namespaced_id for loaded in result.components}
            if expected != set(templates):
                msg = f"{result.bundle} failed to export every loaded component template"
                raise RegistrySnapshotError(msg)
            packages.update(dict.fromkeys(templates, package))
        if bundle_entry_points and not captured:
            msg = "installed bundle entry points produced no discovery evidence"
            raise RegistrySnapshotError(msg)
        merge = getattr(components, "_merge_component_sources", None)
        if merge is None:
            if extensions:
                msg = "the runtime cannot merge its discovered bundle templates"
                raise RegistrySnapshotError(msg)
        else:
            all_types = merge(all_types, {}, extensions)
    try:
        provider_registry = importlib.import_module(f"{namespace}.base.models.provider_registry")
    except ModuleNotFoundError as exc:
        if exc.name != f"{namespace}.base.models.provider_registry":
            raise
    else:
        read_providers = getattr(provider_registry, "get_registry_snapshot", None)
        if read_providers is not None:
            unified = importlib.import_module(f"{namespace}.base.models.unified_models")
            provider_contracts, provider_packages = project_provider_contracts(
                all_types,
                read_providers(validate_catalogs=False).descriptors_by_id,
                unified.apply_provider_variable_config_to_build_config,
                distributions,
                core_distribution,
            )
            if provider_contracts:
                all_types["__provider_contracts__"] = provider_contracts
                packages.update(provider_packages)
    return {
        "format_version": 1,
        "complete": True,
        "distributions": distributions,
        "all_types": all_types,
        "component_packages": packages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="component-registry-home-") as home:
        environment = {
            "PATH": os.defpath,
            "HOME": home,
            "LANGFLOW_CONFIG_DIR": str(Path(home) / "config"),
            "DO_NOT_TRACK": "true",
            # ToolGuard imports LiteLLM, whose pricing table otherwise refreshes
            # over HTTP during import. Use its packaged table for inspection.
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        }
        os.environ.clear()
        os.environ.update(environment)
        _refused_calls.clear()
        sys.addaudithook(_refuse_network)
        result = collect_snapshot()
        if _refused_calls:
            msg = "component discovery attempted a refused operation, so its incomplete registry cannot be exported"
            raise RegistrySnapshotError(msg)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
