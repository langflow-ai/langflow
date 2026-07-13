"""ServiceManager with pluggable service discovery.

Supports multiple discovery mechanisms:
1. Decorator-based registration (@register_service)
2. Config file (lfx.toml / pyproject.toml)
3. Entry points (Python packages)
4. Fallback to noop/minimal implementations
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.capabilities import Capability, ServiceWiringError, Tier, WiringManifestEntry
from lfx.services.config_discovery import (
    get_nested_section,
    get_preferred_config_source,
    load_object_from_import_path,
    load_toml_config,
    resolve_config_dir,
)
from lfx.services.schema import ServiceType
from lfx.utils.concurrency import KeyedMemoryLockManager

if TYPE_CHECKING:
    from lfx.services.base import Service
    from lfx.services.factory import ServiceFactory


class NoFactoryRegisteredError(Exception):
    """Raised when no factory is registered for a service type."""


class NoServiceRegisteredError(Exception):
    """Raised when no service or factory is registered for a service type."""


class ServiceManager:
    """Manages the creation of different services with pluggable discovery."""

    def __init__(self) -> None:
        """Initialize the service manager with empty service and factory registries."""
        self.services: dict[str, Service] = {}
        self.factories: dict[str, ServiceFactory] = {}
        self.service_classes: dict[ServiceType, type[Service]] = {}  # New: direct service class registry
        self._lock = threading.RLock()
        self.keyed_lock = KeyedMemoryLockManager()
        self.factory_registered = False
        self._plugins_discovered = False
        # Active resolution chain, used to detect dependency cycles during
        # recursive service creation (A -> B -> A).
        self._resolving_stack: list[ServiceType] = []

        # Always register settings service
        from lfx.services.settings.factory import SettingsServiceFactory

        self.register_factory(SettingsServiceFactory())

    def register_factories(self, factories: list[ServiceFactory] | None = None) -> None:
        """Register all available service factories."""
        if factories is None:
            return
        for factory in factories:
            try:
                self.register_factory(factory)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error initializing {factory}")
        self.set_factory_registered()

    def are_factories_registered(self) -> bool:
        """Check if the factory is registered."""
        return self.factory_registered

    def set_factory_registered(self) -> None:
        """Set the factory registered flag."""
        self.factory_registered = True

    def register_service_class(
        self,
        service_type: ServiceType,
        service_class: type[Service],
        *,
        override: bool = True,
    ) -> None:
        """Register a service class directly (without factory).

        Args:
            service_type: The service type enum value
            service_class: The service class to register
            override: Whether to override existing registration (default: True)

        Raises:
            ValueError: If attempting to register the settings service (not allowed)
        """
        # Settings service cannot be overridden via plugins
        if service_type == ServiceType.SETTINGS_SERVICE:
            msg = "Settings service cannot be registered via plugins. It is always created using the built-in factory."
            logger.warning(msg)
            raise ValueError(msg)

        # Reject classes that don't implement the declared port for this service
        # type. Applies to every discovery source (decorator, config, entry
        # point), so an unrelated class reusing a service key cannot silently
        # replace a built-in service.
        if not self._validate_port(service_type, service_class):
            return

        if service_type in self.service_classes and not override:
            logger.warning(f"Service {service_type.value} already registered. Use override=True to replace it.")
            return

        if service_type in self.service_classes:
            logger.debug(f"Overriding service registration for {service_type.value}")

        self.service_classes[service_type] = service_class
        logger.debug(f"Registered service class: {service_type.value} -> {service_class.__name__}")

    def register_factory(
        self,
        service_factory: ServiceFactory,
    ) -> None:
        """Registers a new factory with dependencies."""
        service_name = service_factory.service_class.name
        self.factories[service_name] = service_factory

    def get(self, service_name: ServiceType, default: ServiceFactory | None = None) -> Service:
        """Get (or create) a service by its name."""
        with self.keyed_lock.lock(service_name):
            if service_name not in self.services:
                self._create_service(service_name, default)
            return self.services[service_name]

    def _create_service(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Create a new service given its name, handling dependencies."""
        logger.debug(f"Create service {service_name}")

        # Cycle guard: if we are already resolving this service further up the
        # recursion, its dependency graph loops back on itself.
        if service_name in self._resolving_stack:
            chain = " -> ".join(s.value for s in [*self._resolving_stack, service_name])
            msg = f"Dependency cycle detected: {chain}"
            raise ServiceWiringError(msg)

        self._resolving_stack.append(service_name)
        try:
            # Settings service is special - always use factory, never from plugins
            if service_name == ServiceType.SETTINGS_SERVICE:
                self._create_service_from_factory(service_name, default)
                return

            # Try plugin discovery first (if not already done)
            if not self._plugins_discovered:
                # Get config_dir from settings service if available
                config_dir = None
                if ServiceType.SETTINGS_SERVICE in self.services:
                    settings_service = self.services[ServiceType.SETTINGS_SERVICE]
                    if hasattr(settings_service, "settings") and settings_service.settings.config_dir:
                        config_dir = Path(settings_service.settings.config_dir)

                self.discover_plugins(config_dir)

            # Check if we have a direct service class registration (new system)
            if service_name in self.service_classes:
                self._create_service_from_class(service_name)
                return

            # Fall back to factory-based creation (old system)
            self._create_service_from_factory(service_name, default)
        finally:
            self._resolving_stack.pop()

    def _create_service_from_class(self, service_name: ServiceType) -> None:
        """Create a service from a registered service class (new plugin system)."""
        service_class = self.service_classes[service_name]
        logger.debug(f"Creating service from class: {service_name.value} -> {service_class.__name__}")

        # Validate + pre-create declared `requires` dependencies (capabilities +
        # tier layering enforced here, before instantiation).
        self._resolve_requirements(service_name, service_class)

        # Inspect __init__ to determine dependencies
        init_signature = inspect.signature(service_class.__init__)
        dependencies = {}

        for param_name, param in init_signature.parameters.items():
            if param_name == "self":
                continue

            # Try to resolve dependency from type hint first
            dependency_type = None
            if param.annotation != inspect.Parameter.empty:
                dependency_type = self._resolve_service_type_from_annotation(param.annotation)

            # If type hint didn't work, try to resolve from parameter name
            # E.g., param name "settings_service" -> ServiceType.SETTINGS_SERVICE
            if not dependency_type:
                try:
                    dependency_type = ServiceType(param_name)
                except ValueError:
                    # Not a valid service type - skip this parameter if it has a default
                    # Otherwise let it fail during instantiation
                    if param.default == inspect.Parameter.empty:
                        # No default, can't resolve - will fail during instantiation
                        pass
                    continue

            if dependency_type:
                # Check for circular dependency (service depending on itself)
                if dependency_type == service_name:
                    msg = f"Circular dependency detected: {service_name.value} depends on itself"
                    raise RuntimeError(msg)
                # Recursively create dependency if not exists
                # Note: Thread safety is handled by the caller's keyed lock context
                if dependency_type not in self.services:
                    self._create_service(dependency_type)
                dependencies[param_name] = self.services[dependency_type]

        # Create the service instance
        try:
            service_instance = service_class(**dependencies)
            # Don't call set_ready() here - let the service control its own ready state
            self.services[service_name] = service_instance
            logger.debug(f"Service created successfully: {service_name.value}")
        except Exception as exc:
            logger.exception(f"Failed to create service {service_name.value}: {exc}")
            raise

    # ------------------------------------------------------------------
    # Wiring: ports, capabilities, tiers, and boot-time validation
    # ------------------------------------------------------------------

    def _validate_port(self, service_type: ServiceType, service_class: type) -> bool:
        """Return True if ``service_class`` implements the declared port for ``service_type``.

        Services without a declared port (not in ``SERVICE_PORTS``) are not
        validated and always pass. A class that fails is logged and rejected
        (not registered).
        """
        from lfx.services.ports import get_expected_port

        expected = get_expected_port(service_type)
        if expected is None:
            return True
        if isinstance(service_class, type) and issubclass(service_class, expected):
            return True
        logger.warning(
            f"Service class {service_class!r} registered for {service_type.value} is not a subclass of "
            f"{expected.__name__}; skipping registration to avoid replacing the built-in service with an "
            f"incompatible implementation."
        )
        return False

    def _resolve_class(self, service_type: ServiceType) -> type | None:
        """Return the class that *would* be created for ``service_type``, without instantiating.

        Prefers a directly-registered service class (new system), then a
        factory's ``service_class`` (old system). Returns ``None`` if nothing is
        registered for the type. Used by wiring validation and the manifest so
        the whole graph can be reasoned about before any service is built.
        """
        if service_type in self.service_classes:
            return self.service_classes[service_type]
        factory = self.factories.get(service_type)
        if factory is not None:
            return getattr(factory, "service_class", None)
        return None

    def _resolve_requirements(self, service_name: ServiceType, service_class: type) -> None:
        """Validate declared ``requires`` and pre-create the dependencies.

        Raises ``ServiceWiringError`` if a dependency is unregistered, fails a
        capability requirement, or violates the tier layering invariant
        (Tier 1 must not depend on Tier 2). Dependencies that pass validation are
        created in topological order so they exist when the dependent's
        ``__init__`` runs.
        """
        requires = getattr(service_class, "requires", ())
        if not requires:
            return

        service_tier = getattr(service_class, "tier", None)
        for req in requires:
            dep_type = req.service
            dep_class = self._resolve_class(dep_type)
            if dep_class is None:
                msg = (
                    f"{service_name.value} requires {dep_type.value}, but no implementation is registered. "
                    f"Register a {dep_type.value} implementation (config, decorator, or entry point)."
                )
                raise ServiceWiringError(msg)

            # Tier layering: a Tier 1 (infrastructure) service must not depend on
            # a Tier 2 (composed) service.
            dep_tier = getattr(dep_class, "tier", None)
            if service_tier == Tier.INFRASTRUCTURE and dep_tier == Tier.COMPOSED:
                msg = (
                    f"Layering violation: Tier 1 service {service_name.value} declares a dependency on "
                    f"Tier 2 service {dep_type.value}. Infrastructure services may only depend on settings "
                    f"or other infrastructure services."
                )
                raise ServiceWiringError(msg)

            # Capability enforcement: the resolved implementation must provide
            # every capability the dependent requires of it.
            dep_caps = self._capabilities_of(dep_class)
            missing = set(req.capabilities) - dep_caps
            if missing:
                have = ", ".join(sorted(c.value for c in dep_caps)) or "none"
                need = ", ".join(sorted(c.value for c in missing))
                msg = (
                    f"{service_name.value} requires {dep_type.value} to provide capabilities [{need}], but the "
                    f"resolved implementation {dep_class.__name__} provides [{have}]."
                )
                raise ServiceWiringError(msg)

            # Create the dependency (topological order) if not present yet.
            if dep_type not in self.services:
                self._create_service(dep_type)

    @staticmethod
    def _capabilities_of(service_class: type | None) -> set[Capability]:
        """Read a class's declared capabilities defensively (non-Service classes allowed)."""
        return set(getattr(service_class, "capabilities", frozenset()))

    def wiring_manifest(self, *, discover: bool = True) -> dict[ServiceType, WiringManifestEntry]:
        """Resolve every registered service type to its implementation, without instantiating.

        Returns a mapping of ``ServiceType`` -> ``WiringManifestEntry`` describing
        the chosen implementation, its package, tier, and capabilities. Types with
        no registered implementation are omitted. Useful for a ``/health/services``
        endpoint or to eyeball what is actually wired.
        """
        if discover and not self._plugins_discovered:
            self.discover_plugins()

        manifest: dict[ServiceType, WiringManifestEntry] = {}
        for service_type in ServiceType:
            impl = self._resolve_class(service_type)
            if impl is None:
                continue
            tier = getattr(impl, "tier", None)
            manifest[service_type] = WiringManifestEntry(
                service_type=service_type.value,
                impl_class=impl.__name__,
                package=(impl.__module__ or "").split(".")[0],
                tier=int(tier) if tier is not None else 0,
                capabilities=frozenset(self._capabilities_of(impl)),
            )
        return manifest

    def validate_wiring(self, *, discover: bool = True) -> dict[ServiceType, WiringManifestEntry]:
        """Eagerly validate the whole service graph at boot; return the manifest.

        Walks every registered service's ``requires`` edges and enforces
        dependency presence, capability requirements, and the tier layering
        invariant — *without* instantiating any service. Raises
        ``ServiceWiringError`` on the first violation so a misconfigured
        deployment fails before accepting traffic rather than mid-request.
        """
        if discover and not self._plugins_discovered:
            self.discover_plugins()

        manifest = self.wiring_manifest(discover=False)
        for service_type in list(self.service_classes) + list(self.factories):
            # Normalize factory string keys / enum keys to ServiceType.
            try:
                st = service_type if isinstance(service_type, ServiceType) else ServiceType(service_type)
            except ValueError:
                continue
            impl = self._resolve_class(st)
            if impl is None:
                continue
            self._validate_requirements_static(st, impl)
        return manifest

    def _validate_requirements_static(self, service_name: ServiceType, service_class: type) -> None:
        """Validation-only variant of ``_resolve_requirements`` (creates nothing)."""
        requires = getattr(service_class, "requires", ())
        service_tier = getattr(service_class, "tier", None)
        for req in requires:
            dep_class = self._resolve_class(req.service)
            if dep_class is None:
                msg = f"{service_name.value} requires {req.service.value}, but no implementation is registered."
                raise ServiceWiringError(msg)
            dep_tier = getattr(dep_class, "tier", None)
            if service_tier == Tier.INFRASTRUCTURE and dep_tier == Tier.COMPOSED:
                msg = (
                    f"Layering violation: Tier 1 service {service_name.value} declares a dependency on "
                    f"Tier 2 service {req.service.value}."
                )
                raise ServiceWiringError(msg)
            missing = set(req.capabilities) - self._capabilities_of(dep_class)
            if missing:
                have = ", ".join(sorted(c.value for c in self._capabilities_of(dep_class))) or "none"
                need = ", ".join(sorted(c.value for c in missing))
                msg = (
                    f"{service_name.value} requires {req.service.value} to provide capabilities [{need}], but the "
                    f"resolved implementation {dep_class.__name__} provides [{have}]."
                )
                raise ServiceWiringError(msg)

    def wiring_fingerprint(self, *, discover: bool = True) -> str:
        """Stable hash of the wiring's *capabilities* (not implementation classes).

        Two deployments whose services advertise the same per-type capability
        sets produce the same fingerprint even if the concrete classes differ
        (e.g. langflow's memory class vs a cloud plugin's, both persistent). This
        is what makes a builder-vs-production divergence check fire on behavioral
        difference, not on the unavoidable fact that different packages own the
        classes. ``impl_class`` / ``package`` are deliberately excluded.
        """
        manifest = self.wiring_manifest(discover=discover)
        payload = sorted((st.value, sorted(c.value for c in entry.capabilities)) for st, entry in manifest.items())
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()

    def _resolve_service_type_from_annotation(self, annotation) -> ServiceType | None:
        """Resolve a ServiceType from a type annotation.

        Args:
            annotation: The type annotation from __init__ signature

        Returns:
            ServiceType if resolvable, None otherwise
        """
        # Handle string annotations (forward references)
        annotation_name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", None)

        if not annotation_name:
            return None

        # Try to match service class name to ServiceType
        # E.g., "SettingsService" -> ServiceType.SETTINGS_SERVICE
        for service_type in ServiceType:
            # Check if registered service class matches
            if service_type in self.service_classes:
                registered_class = self.service_classes[service_type]
                if registered_class.__name__ == annotation_name:
                    return service_type

            # Check if annotation name matches expected pattern
            # E.g., "SettingsService" -> "settings_service"
            expected_name = annotation_name.replace("Service", "").lower() + "_service"
            if service_type.value == expected_name:
                return service_type

        return None

    def _create_service_from_factory(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Create a service from a factory (old system)."""
        self._validate_service_creation(service_name, default)

        if service_name == ServiceType.SETTINGS_SERVICE:
            from lfx.services.settings.factory import SettingsServiceFactory

            factory = SettingsServiceFactory()
            if factory not in self.factories:
                self.register_factory(factory)
        else:
            factory = self.factories.get(service_name)

        # Create dependencies first
        if factory is None and default is not None:
            self.register_factory(default)
            factory = default
        if factory is None:
            msg = f"No factory registered for {service_name}"
            raise NoFactoryRegisteredError(msg)
        for dependency in factory.dependencies:
            if dependency not in self.services:
                self._create_service(dependency)

        # Collect the dependent services
        dependent_services = {dep.value: self.services[dep] for dep in factory.dependencies}

        # Create the actual service
        self.services[service_name] = self.factories[service_name].create(**dependent_services)
        self.services[service_name].set_ready()

    def _validate_service_creation(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Validate whether the service can be created."""
        if service_name == ServiceType.SETTINGS_SERVICE:
            return
        if service_name not in self.factories and default is None:
            msg = f"No factory registered for the service class '{service_name.name}'"
            raise NoFactoryRegisteredError(msg)

    def update(self, service_name: ServiceType) -> None:
        """Update a service by its name."""
        if service_name in self.services:
            logger.debug(f"Update service {service_name}")
            self.services.pop(service_name, None)
            self.get(service_name)

    async def teardown(self, *, raise_on_error: bool = False) -> None:
        """Teardown all the services.

        Args:
            raise_on_error: When True, still attempt every teardown, but re-raise the
                first error after the table is cleared. Default False logs failures only.
        """
        errors: list[tuple[str, Exception]] = []
        for service in list(self.services.values()):
            if service is None:
                continue
            logger.debug(f"Teardown service {service.name}")
            try:
                teardown_result = service.teardown()
                if asyncio.iscoroutine(teardown_result):
                    await teardown_result
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Error in teardown of {service.name}", exc_info=exc)
                errors.append((service.name, exc))

        # Adapter registries own singleton adapter instances and must also be cleaned up.
        try:
            from lfx.services.adapters.registry import teardown_all_adapter_registries

            await teardown_all_adapter_registries()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error during adapter registry teardown: {exc}", exc_info=True)
            errors.append(("adapter_registries", exc))

        self.services = {}
        self.factories = {}
        # ``teardown`` empties the factory registry, so the "registered" flag has
        # to drop too: get_service() re-registers factories only when
        # are_factories_registered() is False. Leaving it set after a teardown
        # makes the next lookup skip re-registration and raise
        # NoFactoryRegisteredError.
        self.factory_registered = False

        if raise_on_error and errors:
            names = ", ".join(name for name, _ in errors)
            msg = f"Service teardown failed for: {names}"
            raise RuntimeError(msg) from errors[0][1]

    @classmethod
    def get_factories(cls) -> list[ServiceFactory]:
        """Auto-discover and return all service factories."""
        from lfx.services.factory import ServiceFactory
        from lfx.services.schema import ServiceType

        service_names = [ServiceType(service_type).value.replace("_service", "") for service_type in ServiceType]
        base_module = "lfx.services"
        factories = []

        for name in service_names:
            try:
                module_name = f"{base_module}.{name}.factory"
                module = importlib.import_module(module_name)

                # Find all classes in the module that are subclasses of ServiceFactory
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if isinstance(obj, type) and issubclass(obj, ServiceFactory) and obj is not ServiceFactory:
                        factories.append(obj())
                        break

            except Exception:  # noqa: BLE001, S110
                # This is expected during initial service discovery - some services
                # may not have factories yet or depend on settings service being ready first
                # Intentionally suppressed to avoid startup noise - not an error condition
                pass

        return factories

    def discover_plugins(self, config_dir: Path | None = None) -> None:
        """Discover and register service plugins from multiple sources.

        Decorator-registered services are already in ``service_classes``
        at this point (they register at import time via ``@register_service``).

        This method discovers two additional sources:

        1. Entry points (``override=False`` — won't overwrite decorators)
        2. Config files (``override=True`` — will overwrite decorators)

        Effective precedence: config files > decorators > entry points.

        Args:
            config_dir: Directory to search for config files.
                       If None, tries to use settings_service.settings.config_dir,
                       then falls back to current working directory.

        Note:
            The settings service cannot be overridden via plugins and is always
            created using the built-in factory.
        """
        with self._lock:
            if self._plugins_discovered:
                logger.debug("Plugins already discovered, skipping...")
                return

            settings_service = self.services.get(ServiceType.SETTINGS_SERVICE)
            config_dir = resolve_config_dir(config_dir, settings_service=settings_service)

            logger.debug(f"Starting plugin discovery (config_dir: {config_dir})...")

            # 1. Discover from entry points
            self._discover_from_entry_points()

            # 2. Discover from config files
            self._discover_from_config(config_dir)

            self._plugins_discovered = True
            logger.debug(f"Plugin discovery complete. Registered services: {list(self.service_classes.keys())}")

    def _discover_from_entry_points(self) -> None:
        """Discover services from Python entry points."""
        from importlib.metadata import entry_points

        try:
            eps = entry_points(group="lfx.services")
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to enumerate entry points for group='lfx.services'. "
                "Entry-point-based service discovery will be skipped."
            )
            return

        for ep in eps:
            try:
                service_class = ep.load()
                # Entry point name should match ServiceType enum value.
                service_type = ServiceType(ep.name)
                # Port validation (must subclass the declared port) is enforced
                # centrally in register_service_class for every discovery source,
                # so an unrelated class reusing this entry-point name cannot
                # silently replace a built-in service.
                self.register_service_class(service_type, service_class, override=False)
                logger.debug(f"Loaded service from entry point: {ep.name}")
            except (ValueError, AttributeError) as exc:
                logger.warning(f"Failed to load entry point {ep.name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                # Authz plugin failures are operator-visible — silent
                # degradation to the OSS pass-through is exactly the kind
                # of behavior change we want noisy.
                logger.warning(f"Error loading entry point {ep.name}: {exc}")

    def _discover_from_config(self, config_dir: Path) -> None:
        """Discover services from config files (lfx.toml / pyproject.toml)."""
        source = get_preferred_config_source(
            config_dir,
            lfx_root_path=("services",),
            pyproject_root_path=("tool", "lfx", "services"),
        )
        if source is None:
            return
        self._load_services_from_config(*source)

    def _load_services_from_config(self, config_path: Path, root_path: tuple[str, ...]) -> None:
        """Load service registrations from config section."""
        config = load_toml_config(config_path)
        if config is None:
            return

        services = get_nested_section(config, root_path) or {}
        for service_key, service_path in services.items():
            self._register_service_from_path(service_key, service_path)

        if config_path.name == "lfx.toml" or services:
            logger.debug(f"Loaded {len(services)} services from {config_path}")

    def _register_service_from_path(self, service_key: str, service_path: str) -> None:
        """Register a service from a module:class path string.

        Args:
            service_key: ServiceType enum value (e.g., "database_service")
            service_path: Import path (e.g., "langflow.services.database.service:DatabaseService")
        """
        try:
            # Validate service_key matches ServiceType enum
            service_type = ServiceType(service_key)
        except ValueError:
            logger.warning(f"Invalid service key '{service_key}' - must match ServiceType enum value")
            return

        service_class = load_object_from_import_path(
            service_path,
            object_kind="service",
            object_key=service_key,
        )
        if service_class is None:
            return

        self.register_service_class(service_type, service_class, override=True)
        logger.debug(f"Registered service from config: {service_key} -> {service_path}")


# Global variables for lazy initialization
_service_manager: ServiceManager | None = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """Get or create the service manager instance using lazy initialization.

    This function ensures thread-safe lazy initialization of the service manager,
    preventing automatic service creation during module import.

    Returns:
        ServiceManager: The singleton service manager instance.
    """
    global _service_manager  # noqa: PLW0603
    if _service_manager is None:
        with _service_manager_lock:
            if _service_manager is None:
                _service_manager = ServiceManager()
    return _service_manager
