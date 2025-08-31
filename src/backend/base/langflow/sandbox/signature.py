"""Component signature verification system for trust-based sandbox execution."""

from __future__ import annotations

import ast
import hashlib
import hmac
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlmodel import Session

from .policies import SecurityPolicy


@dataclass
class ComponentSignature:
    """Represents a component's cryptographic signature for integrity verification."""

    path: str
    signature: str
    timestamp: datetime
    version: str = "1.0"
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def create(cls, component_path: str, code: str, signing_key: str | None = None) -> ComponentSignature:
        """Create a new component signature."""
        normalized_code = cls._normalize_code(code)
        signature = cls._generate_signature(normalized_code, signing_key)

        return cls(
            path=component_path,
            signature=signature,
            timestamp=datetime.utcnow(),
            metadata={
                "normalized_length": len(normalized_code),
                "original_length": len(code)
            }
        )

    @staticmethod
    def _normalize_code(code: str) -> str:
        """Normalize code by removing comments and standardizing whitespace."""
        try:
            # Parse and unparse to get canonical representation
            tree = ast.parse(code)
            return ast.unparse(tree)
        except SyntaxError as e:
            logger.warning(f"Could not normalize code due to syntax error: {e}")
            # Fallback: just strip and normalize whitespace
            lines = [line.strip() for line in code.split("\n") if line.strip()]
            return "\n".join(lines)

    @staticmethod
    def _generate_signature(code: str, signing_key: str | None = None) -> str:
        """Generate HMAC signature for code."""
        return hmac.new(
            signing_key.encode("utf-8"),
            code.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def verify(self, code: str, signing_key: str | None = None) -> bool:
        """Verify that the code matches this signature."""
        try:
            normalized_code = self._normalize_code(code)
            calculated_signature = self._generate_signature(normalized_code, signing_key)

            return hmac.compare_digest(calculated_signature, self.signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComponentSignature:
        """Create from dictionary."""
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ComponentSecurityManager:
    """Manages component signatures and security policies for trust-based sandbox execution."""

    def __init__(self, security_policy: SecurityPolicy | None = None, db_session: Session | None = None):
        logger.info("ComponentSecurityManager initialized with database signature storage")
        self.sandbox_supported_components: set[str] = set()  # Track which components support sandboxing
        self.security_policy = security_policy or SecurityPolicy()
        self.db_session = db_session

        # Use the main Langflow auth secret key for component signing
        from langflow.services.settings.auth import AuthSettings
        auth_settings = AuthSettings()
        self.signing_key = auth_settings.SECRET_KEY.get_secret_value()

        # Generate signatures for built-in components on every startup
        if self.db_session:
            self._initialize_builtin_signatures()
    def _initialize_builtin_signatures(self) -> None:
        """Initialize component signatures with database storage:
        1. If LANGFLOW_SANDBOX_DEV_MODE=true, truncate the signatures table
        2. Scan components and generate new signatures
        3. Upsert new signatures to database
        """
        # Check if we're in sandbox development mode
        sandbox_dev_mode = os.getenv("LANGFLOW_SANDBOX_DEV_MODE") == "true"

        if sandbox_dev_mode and self.db_session:
            logger.warning("SANDBOX DEV MODE: Truncating signatures table to regenerate fresh signatures")
            try:
                from langflow.services.database.models.signature.model import Component
                # Delete all existing signatures
                self.db_session.query(Component).delete()
                self.db_session.commit()
                logger.info("Successfully truncated signatures table")
            except Exception as e:
                logger.error(f"Failed to truncate signatures table: {e}")
                self.db_session.rollback()

        # Load the list of sandbox-supported components
        from .sandbox_manifest import get_supported_component_class_names
        supported_component_class_names = get_supported_component_class_names()

        # Scan components and generate current signatures
        try:
            logger.info("Scanning codebase for component classes")

            # Get components directory from settings service
            from langflow.services.deps import get_settings_service
            settings_service = get_settings_service()
            components_paths = settings_service.settings.components_path

            components_dir = None
            for components_path in components_paths:
                if os.path.exists(components_path):
                    components_dir = components_path
                    logger.debug(f"Found components directory: {components_dir}")
                    break

            if not components_dir:
                logger.warning(f"Could not find components directory for signature generation. Searched paths: {components_paths}")
                return

            # Step 3: Scan and upsert new signatures
            generated_count = self._scan_and_upsert_signatures(components_dir, supported_component_class_names)

            # Log the results
            storage_stats = self._get_database_stats()
            logger.info(f"Scanned {generated_count} components, stored {storage_stats['unique_components']} unique components")
            logger.info(f"Storage stats: {storage_stats['unique_components']} components, {storage_stats['total_versions']} total versions")

            logger.debug(f"SCAN COMPLETE: scanned {generated_count}, stored {storage_stats['unique_components']} unique components, {storage_stats['total_versions']} total versions", flush=True)

        except Exception as e:
            logger.error(f"Failed to initialize component signatures: {e}")
            import traceback
            traceback.print_exc()


    def _scan_and_upsert_signatures(self, components_dir: str, supported_components: list) -> int:
        """Scan components and upsert new signatures to database."""
        if not self.db_session:
            return 0

        import ast

        from langflow.services.database.models.signature.crud import component_version_exists, create_component
        from langflow.services.database.models.signature.model import Component as DBComponent

        generated_count = 0
        scanned_files = 0
        found_classes = 0

        logger.info(f"Starting comprehensive component scan of {components_dir}")

        for root, dirs, files in os.walk(components_dir):
            # Skip __pycache__, .git, and other non-source directories
            dirs[:] = [d for d in dirs if not d.startswith("__pycache__") and not d.startswith(".")]

            for file in files:
                if not file.endswith(".py") or file.startswith("__"):
                    continue

                file_path = os.path.join(root, file)
                scanned_files += 1

                try:
                    with open(file_path, encoding="utf-8") as f:
                        code = f.read()

                    # Parse the AST to find ALL classes
                    try:
                        tree = ast.parse(code)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                found_classes += 1

                                # Check if it looks like a component class
                                if self._is_component_class(node, code):
                                    # Get the actual component name (from name attribute or class name)
                                    component_name = self._get_component_name(node.name, file_path, code)

                                    # Use the component name as the path
                                    component_path = component_name

                                    # Check if component is in the supported list (by class name)
                                    if node.name in supported_components:
                                        self.sandbox_supported_components.add(component_path)
                                        logger.debug(f"Component {component_path} (class: {node.name}) is in sandbox supported list")

                                    # Get component version (try to extract from class or default to 1.0)
                                    component_version = self._extract_component_version(node, code)

                                    # Extract folder from file path
                                    folder = self._extract_folder(file_path, components_dir)

                                    # Generate signature for the entire file's code
                                    signature = ComponentSignature.create(component_path, code, self.signing_key)

                                    # Check if this exact component version already exists
                                    if not component_version_exists(self.db_session, component_path, component_version, folder):
                                        # Create database model with full code storage
                                        db_component = DBComponent(
                                            component_path=component_path,
                                            folder=folder,
                                            version=component_version,
                                            code=code,  # Store full source code
                                            signature=signature.signature
                                        )
                                        create_component(self.db_session, db_component)
                                        logger.debug(f"Added new component version {folder}/{component_path} v{component_version}")

                                        generated_count += 1

                                        # Get relative path for logging
                                        rel_path = os.path.relpath(file_path, components_dir)
                                        sandbox_supported = node.name in supported_components
                                        logger.debug(f"✓ Generated signature for {component_path} v{component_version} from {rel_path} (class={node.name}, sandbox_supported={sandbox_supported})")
                                    else:
                                        logger.debug(f"Component version {folder}/{component_path} v{component_version} already exists, skipping")

                    except SyntaxError as e:
                        # Log syntax errors but continue
                        rel_path = os.path.relpath(file_path, components_dir)
                        logger.debug(f"Skipping {rel_path} due to syntax error: {e}")
                        continue

                except Exception as e:
                    rel_path = os.path.relpath(file_path, components_dir)
                    logger.debug(f"Could not process {rel_path}: {e}")
                    continue

        logger.info(f"Scan complete: {scanned_files} files, {found_classes} total classes, {generated_count} new signatures added")

        # Log sandbox supported components with details
        if self.sandbox_supported_components:
            from .sandbox_manifest import SANDBOX_MANIFEST

            logger.info(f"Components that support sandboxing ({len(self.sandbox_supported_components)}): {sorted(self.sandbox_supported_components)}")

            # Log detailed information about each supported component
            for component_config in SANDBOX_MANIFEST:
                component_path = component_config.name
                if component_path in self.sandbox_supported_components:
                    logger.info(f"  - {component_config.name}: {component_config.notes}")
        else:
            logger.info("No components explicitly marked as supporting sandboxing")

        return generated_count

    def _is_component_class(self, node: ast.ClassDef, code: str) -> bool:
        """Check if an AST class node represents a component using comprehensive patterns."""
        class_name = node.name

        # 1. Class name patterns (most reliable indicator)
        component_name_patterns = [
            "Component",      # Standard component suffix
            "Tool",          # Tool components
            "Agent",         # Agent components
            "Model",         # Model components
            "Embeddings",    # Embedding components
            "Vectorstore",   # Vector store components
            "Loader",        # Document loader components
            "Splitter",      # Text splitter components
            "Retriever",     # Retriever components
            "Memory",        # Memory components
            "Chain",         # Chain components
            "Prompt"         # Prompt components
        ]

        for pattern in component_name_patterns:
            if class_name.endswith(pattern):
                return True

        # 2. Check inheritance from component base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_patterns = [
                    "Component", "CustomComponent", "BaseComponent",
                    "LangChainComponent", "ProcessingComponent",
                    "InputComponent", "OutputComponent",
                    "ToolComponent", "AgentComponent"
                ]
                for pattern in base_patterns:
                    if pattern in base.id:
                        return True

            elif isinstance(base, ast.Attribute):
                # Handle cases like langflow.Component, custom.BaseComponent
                base_attrs = ["Component", "CustomComponent", "BaseComponent",
                             "ToolComponent", "AgentComponent"]
                if base.attr in base_attrs:
                    return True

        # 3. Check for component-specific decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if "component" in decorator.id.lower():
                    return True
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if "component" in decorator.func.id.lower():
                    return True

        # 4. Check for specific attributes that indicate a component
        component_attributes = [
            "display_name", "description", "icon", "inputs", "outputs",
            "code_class_base_inheritance", "_code_class_base_inheritance"
        ]

        for attr_node in node.body:
            if isinstance(attr_node, ast.Assign):
                for target in attr_node.targets:
                    if isinstance(target, ast.Name) and target.id in component_attributes:
                        return True

        # 5. Look for component-specific methods
        component_methods = ["build", "run", "execute", "process"]
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in component_methods:
                return True

        return False

    def _get_component_name(self, name: str, file_path: str, code: str) -> str:
        """Get the component's name attribute by trying to instantiate it."""
        try:
            # Try to dynamically import and instantiate the component to get its name attribute
            import importlib.util

            # Create a temporary module from the code
            spec = importlib.util.spec_from_loader(f"temp_module_{name}", loader=None)
            if spec is None:
                return name

            module = importlib.util.module_from_spec(spec)

            # Execute the code in the module's namespace
            exec(code, module.__dict__)

            # Get the class from the module
            if hasattr(module, name):
                component_class = getattr(module, name)

                # Try to instantiate it and get the name attribute
                try:
                    instance = component_class()
                    if hasattr(instance, "name") and instance.name:
                        return instance.name
                except Exception:
                    # If instantiation fails, try to get the name from class attributes
                    if hasattr(component_class, "name") and component_class.name:
                        return component_class.name

        except Exception as e:
            logger.debug(f"Could not get component name for {name} from {file_path}: {e}")

        # Fallback to class name
        return name

    def _extract_component_version(self, node: ast.ClassDef, code: str) -> str:
        """Extract component version from class definition or default to 1.0."""
        # Look for version class variable in the AST
        for item in node.body:
            # Handle simple assignment: version = "1.0"
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "version":
                        # Try to extract the version value
                        if isinstance(item.value, ast.Constant):
                            return str(item.value.value)
                        if isinstance(item.value, ast.Str):  # Python < 3.8 compatibility
                            return item.value.s

            # Handle annotated assignment: version: ClassVar[str] = "1.0"
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and item.target.id == "version":
                    if item.value:  # Has a value assigned
                        if isinstance(item.value, ast.Constant):
                            return str(item.value.value)
                        if isinstance(item.value, ast.Str):  # Python < 3.8 compatibility
                            return item.value.s

        # Default version if not found
        return "1.0"

    def _extract_folder(self, file_path: str, components_dir: str) -> str:
        """Extract the folder name from the file path."""
        # Get relative path from components directory
        rel_path = os.path.relpath(file_path, components_dir)

        # Extract subdirectory (e.g., "search/google_serper_api.py" -> "search")
        path_parts = rel_path.split(os.sep)

        if len(path_parts) > 1:
            # Has subdirectory
            return path_parts[0]
        # Top-level component
        return "root"



    def supports_sandboxing(self, path: str) -> bool:
        """Check if a component supports sandboxing."""
        from .sandbox_manifest import SANDBOX_MANIFEST

        # Custom components always support sandboxing
        if path.startswith("custom."):
            return True

        # Check if built-in component is in the manifest
        # We check both class name and component name since components are stored by their name property
        for component_manifest in SANDBOX_MANIFEST:
            if component_manifest.class_name == path or component_manifest.name == path:
                return True

        return False

    def is_force_sandbox(self, path: str) -> bool:
        """Check if a component is forced to execute in sandbox mode."""
        from .sandbox_manifest import SANDBOX_MANIFEST

        # Custom components are never forced (they're already untrusted)
        if path.startswith("custom."):
            return False

        # Check if built-in component has force_sandbox=True in the manifest
        # We check both class name and component name since components are stored by their name property
        for component_manifest in SANDBOX_MANIFEST:
            if component_manifest.class_name == path or component_manifest.name == path:
                return component_manifest.force_sandbox

        return False



    def verify_component_signature(self, path: str, code: str, log_verification: bool = True) -> bool:
        """Verify code against any historical signature for the component.
        This prevents breaking existing flows when components are updated.
        
        Args:
            path: Component path/name
            code: Component source code
            log_verification: Whether to log successful verifications (default True)
        """
        if not self.db_session:
            return False

        from langflow.services.database.models.signature.crud import get_components_by_path

        # Get all versions for this component (including historical ones)
        db_components = get_components_by_path(self.db_session, path)

        if not db_components:
            return False

        # Try to verify against any version
        for db_component in db_components:
            try:
                # Verify the signature directly against the stored code
                normalized_code = ComponentSignature._normalize_code(code)
                calculated_signature = ComponentSignature._generate_signature(normalized_code, self.signing_key)

                if hmac.compare_digest(calculated_signature, db_component.signature):
                    if log_verification:
                        logger.debug(f"Component {path} verified against version {db_component.version}")
                    return True
            except Exception as e:
                logger.debug(f"Verification error for {path} with version {db_component.version} from {db_component.created_at}: {e}")
                continue
        return False

    def _get_database_stats(self) -> dict[str, int]:
        """Get statistics about stored components from database."""
        if not self.db_session:
            return {"components": 0, "total_signatures": 0, "avg_signatures_per_component": 0}

        from langflow.services.database.models.signature.crud import get_component_stats
        return get_component_stats(self.db_session)
