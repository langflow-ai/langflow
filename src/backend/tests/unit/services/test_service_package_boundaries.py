"""Static boundary checks for the standalone ``services`` package."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from lfx.services.schema import ServiceType

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

SERVICES_ROOT = Path(__file__).resolve().parents[4] / "langflow-services" / "src" / "services"
SERVICES_PYPROJECT = SERVICES_ROOT.parent.parent / "pyproject.toml"

# Selectable backends / providers are flat extras (bundles-style), not
# ``services/<name>/`` package directories. Use <service>-<backend> only when
# the backend needs distinct third-party deps.
_BACKEND_EXTRAS = frozenset(
    {
        "database-sqlite",
        "database-postgresql",
        "cache-redis",
        "job-queue-redis",
        "storage-s3",
        "variable-kubernetes",
        "task-celery",
        "tracing-langfuse",
        "tracing-langwatch",
        "tracing-langsmith",
        "tracing-arize",
        "tracing-openinference",
        "tracing-opik",
        "tracing-traceloop",
        "tracing-openlayer",
        "tracing-all",
        "deployment-watsonx-orchestrate",
    }
)
_META_EXTRAS = frozenset({"all", "tracing-all", "production"})
# Services whose install surface is only <service>-<backend> extras (no empty shell).
_SERVICES_VIA_BACKEND_ONLY = frozenset({"database"})
# Production prefers these backends over empty shells / sqlite / local disk.
_PRODUCTION_BACKEND_EXTRAS = frozenset(
    {
        "database-postgresql",
        "cache-redis",
        "job-queue-redis",
        "storage-s3",
        "task-celery",
    }
)
# Services covered by a production backend (no empty shell needed in [production]).
_PRODUCTION_BACKEND_SERVICE_PACKAGES = frozenset(
    {
        "database",
        "cache",
        "job_queue",
        "storage",
        "task",
    }
)


def _load_pyproject() -> dict:
    return tomllib.loads(SERVICES_PYPROJECT.read_text(encoding="utf-8"))


_PYPROJECT = _load_pyproject()
_EXTRAS = _PYPROJECT["project"]["optional-dependencies"]
_SERVICE_EXTRAS = frozenset(name for name in _EXTRAS if name not in _BACKEND_EXTRAS | _META_EXTRAS)
_SERVICE_EXTRA_PACKAGES = frozenset(name.replace("-", "_") for name in _SERVICE_EXTRAS)

# Must stay aligned with ``services.factory._LFX_OWNED``.
_LFX_OWNED = frozenset({"mcp_composer", "executor", "extension_events", "settings"})
_ALLOWED_ROOT_MODULES = frozenset({"__init__.py", "bootstrap.py", "deps.py", "factory.py", "providers.py"})
_ALLOWED_NON_SERVICE_DIRS = frozenset({"adapters", "__pycache__"})


def _service_package_name(service_type: ServiceType) -> str:
    """Map a ServiceType to its ``services.<name>`` package directory."""
    return service_type.value.replace("_service", "")


def _langflow_owned_service_packages() -> list[str]:
    return sorted(
        name for service_type in ServiceType if (name := _service_package_name(service_type)) not in _LFX_OWNED
    )


def _iter_service_source_files() -> list[Path]:
    if not SERVICES_ROOT.exists():
        return []
    return [path for path in SERVICES_ROOT.rglob("*.py") if "__pycache__" not in path.parts]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", _iter_service_source_files())
def test_services_package_has_no_langflow_imports(path: Path) -> None:
    """Runtime modules under ``services`` must never import ``langflow``."""
    violations = [
        module for module in _imported_modules(path) if module == "langflow" or module.startswith("langflow.")
    ]
    assert not violations, f"{path.relative_to(SERVICES_ROOT.parent.parent)} imports {violations}"


@pytest.mark.parametrize("package_name", _langflow_owned_service_packages())
def test_each_langflow_owned_service_has_subpackage(package_name: str) -> None:
    """Every Langflow-owned ServiceType lives under ``services/<name>/``."""
    package_dir = SERVICES_ROOT / package_name
    assert package_dir.is_dir(), f"missing service subpackage: services.{package_name}"
    assert (package_dir / "__init__.py").is_file(), f"services.{package_name} missing __init__.py"
    assert (package_dir / "service.py").is_file(), f"services.{package_name} missing service.py"
    assert (package_dir / "factory.py").is_file(), f"services.{package_name} missing factory.py"


def test_pyproject_has_one_extra_per_langflow_owned_service() -> None:
    """Expose a service-shell extra for packages that are not backend-only."""
    expected = frozenset(_langflow_owned_service_packages()) - _SERVICES_VIA_BACKEND_ONLY
    assert expected == _SERVICE_EXTRA_PACKAGES


def test_database_is_backend_extras_only() -> None:
    """Database has no empty shell; install via database-sqlite / database-postgresql."""
    assert "database" not in _EXTRAS
    assert "database-sqlite" in _EXTRAS
    assert "database-postgresql" in _EXTRAS


def test_pyproject_declares_known_backend_extras() -> None:
    """Selectable backends/providers use a fixed flat-extra allowlist."""
    declared = frozenset(name for name in _EXTRAS if name in _BACKEND_EXTRAS)
    assert declared == _BACKEND_EXTRAS


def test_production_extra_covers_every_service_preferring_prod_backends() -> None:
    """``[production]`` = prod backends where they exist, else default shells."""
    assert "production" in _EXTRAS
    expected_backends = {f"langflow-services[{name}]" for name in _PRODUCTION_BACKEND_EXTRAS}
    expected_shells = {
        f"langflow-services[{package_name.replace('_', '-')}]"
        for package_name in _langflow_owned_service_packages()
        if package_name not in _PRODUCTION_BACKEND_SERVICE_PACKAGES
    }
    assert set(_EXTRAS["production"]) == expected_backends | expected_shells
    assert "langflow-services[database-sqlite]" not in _EXTRAS["production"]


def test_all_extra_aggregates_service_and_backend_extras() -> None:
    """``langflow-services[all]`` includes every service shell and backend extra."""
    expected_services = {
        f"langflow-services[{package_name.replace('_', '-')}]"
        for package_name in _langflow_owned_service_packages()
        if package_name not in _SERVICES_VIA_BACKEND_ONLY
    }
    all_entries = set(_EXTRAS["all"])
    assert expected_services <= all_entries
    assert "langflow-services[database-sqlite]" in all_entries
    assert "langflow-services[database-postgresql]" in all_entries
    assert "langflow-services[deployment-watsonx-orchestrate]" in all_entries
    assert "langflow-services[tracing-all]" in all_entries
    non_tracing = {
        f"langflow-services[{name}]"
        for name in _BACKEND_EXTRAS
        if name != "tracing-all" and not name.startswith("tracing-")
    }
    assert non_tracing <= all_entries


def test_service_package_entry_point_exposes_bootstrap_registrar() -> None:
    """Advertise this service-package root using the LFX entry-point group."""
    entry_points = _PYPROJECT["project"]["entry-points"]["lfx.service-packages"]
    assert entry_points == {"langflow-services": "services.bootstrap:register_all_service_factories"}


def test_jobs_service_maps_to_jobs_package() -> None:
    r"""``JOB_SERVICE = "jobs_service"`` resolves to the ``jobs`` package."""
    assert _service_package_name(ServiceType.JOB_SERVICE) == "jobs"
    assert (SERVICES_ROOT / "jobs" / "service.py").is_file()
    assert (SERVICES_ROOT / "jobs" / "factory.py").is_file()


def test_root_modules_are_shared_infrastructure_only() -> None:
    """Concrete implementations must not live as top-level ``services/*.py`` files."""
    root_modules = sorted(path.name for path in SERVICES_ROOT.glob("*.py"))
    unexpected = [name for name in root_modules if name not in _ALLOWED_ROOT_MODULES]
    assert not unexpected, f"unexpected root modules (move into a service subpackage): {unexpected}"


def test_top_level_dirs_are_service_packages_or_allowed_exceptions() -> None:
    """Top-level dirs must be ServiceType packages, adapters/, or tooling caches."""
    top_level_dirs = {path.name for path in SERVICES_ROOT.iterdir() if path.is_dir()}
    expected_packages = frozenset(_langflow_owned_service_packages())
    unexpected = sorted(top_level_dirs - expected_packages - _ALLOWED_NON_SERVICE_DIRS)
    assert not unexpected, f"unexpected top-level dirs under services/: {unexpected}"


def test_lfx_owned_services_are_not_extracted() -> None:
    """LFX-owned ServiceTypes must not have concrete packages in this distribution."""
    for name in sorted(_LFX_OWNED):
        assert not (SERVICES_ROOT / name).exists(), f"LFX-owned service incorrectly extracted: services.{name}"


def test_factory_lfx_owned_set_matches_boundary_allowlist() -> None:
    """Keep the layout test and factory inference ownership sets in sync."""
    import services.factory as services_factory

    assert frozenset(services_factory._LFX_OWNED) == _LFX_OWNED
