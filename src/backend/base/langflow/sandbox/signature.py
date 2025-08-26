"""Component signature verification system for trust-based sandbox execution."""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Any, List
from dataclasses import dataclass, asdict

from loguru import logger

from .sandbox_context import ComponentTrustLevel
from .policies import SecurityPolicy


@dataclass
class ComponentSignature:
    """Represents a component's cryptographic signature for integrity verification."""
    
    path: str
    code_hash: str
    signature: str
    timestamp: datetime
    version: str = "1.0"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def create(cls, component_path: str, code: str, signing_key: Optional[str] = None) -> ComponentSignature:
        """Create a new component signature."""
        normalized_code = cls._normalize_code(code)
        code_hash = cls._calculate_hash(normalized_code)
        signature = cls._generate_signature(normalized_code, signing_key)
        
        return cls(
            path=component_path,
            code_hash=code_hash,
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
            lines = [line.strip() for line in code.split('\n') if line.strip()]
            return '\n'.join(lines)
    
    @staticmethod
    def _calculate_hash(code: str) -> str:
        """Calculate SHA-256 hash of code."""
        return hashlib.sha256(code.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _generate_signature(code: str, signing_key: Optional[str] = None) -> str:
        """Generate HMAC signature for code."""
        return hmac.new(
            signing_key.encode('utf-8'),
            code.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify(self, code: str, signing_key: Optional[str] = None) -> bool:
        """Verify that the code matches this signature."""
        try:
            normalized_code = self._normalize_code(code)
            calculated_hash = self._calculate_hash(normalized_code)
            calculated_signature = self._generate_signature(normalized_code, signing_key)
            
            hash_match = calculated_hash == self.code_hash
            signature_match = hmac.compare_digest(calculated_signature, self.signature)
            
            return hash_match and signature_match
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ComponentSignature:
        """Create from dictionary."""
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ComponentSecurityManager:
    """Manages component signatures and security policies for trust-based sandbox execution."""
    
    def __init__(self, security_policy: Optional[SecurityPolicy] = None):
        logger.info("ComponentSecurityManager initialized with persistent signature storage")
        self.signatures: Dict[str, ComponentSignature] = {}
        self.sandbox_supported_components: Set[str] = set()  # Track which components support sandboxing
        self.security_policy = security_policy or SecurityPolicy()

        # Use the main Langflow auth secret key for component signing
        from langflow.services.settings.auth import AuthSettings
        auth_settings = AuthSettings()
        self.signing_key = auth_settings.SECRET_KEY.get_secret_value()
        
        # Initialize persistent storage
        from .signature_storage import ComponentSignatureStorage
        self.storage = ComponentSignatureStorage()
        
        # Generate signatures for built-in components on every startup
        self._initialize_builtin_signatures()
    def _initialize_builtin_signatures(self) -> None:
        """
        Initialize component signatures with persistent storage:
        1. Load existing signatures from storage into memory
        2. Scan components and generate new signatures
        3. Upsert new signatures to storage
        4. Load final list (including historical versions) into memory
        """
        
        # Load the list of sandbox-supported components
        from .sandbox_manifest import SANDBOX_MANIFEST, get_supported_component_class_names
        supported_component_class_names = get_supported_component_class_names()
        
        # Step 1: Load existing signatures from storage
        logger.info("Loading existing signatures from persistent storage")
        self._load_signatures_from_storage()
        
        # Step 2: Scan components and generate current signatures
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
            
            # Step 4: Reload all signatures (including historical) into memory
            self._load_signatures_from_storage()
            
            # Log the results with key status warning
            storage_stats = self.storage.get_stats()
            logger.info(f"Scanned {generated_count} components, stored {storage_stats['components']} unique components")
            logger.info(f"Storage stats: {storage_stats['components']} components, {storage_stats['total_signatures']} total signatures")
            
            # Warn if seeing signature accumulation (could indicate key instability)
            if storage_stats['total_signatures'] > storage_stats['components'] * 2:
                avg_sigs = storage_stats['avg_signatures_per_component']
                logger.warning(f"⚠️  Signature accumulation detected: {avg_sigs:.1f} signatures per component")
                logger.warning("This could indicate signing key instability or component code changes")
            
            logger.debug(f"SCAN COMPLETE: scanned {generated_count}, stored {storage_stats['components']} unique components, {storage_stats['total_signatures']} total signatures", flush=True)
                
        except Exception as e:
            logger.error(f"Failed to initialize component signatures: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_signatures_from_storage(self) -> None:
        """Load all signatures from persistent storage into memory."""
        self.signatures.clear()
        
        for component_path in self.storage.get_all_component_paths():
            # Load the most recent signature for each component
            latest_signature = self.storage.get_latest_signature(component_path)
            if latest_signature:
                self.signatures[component_path] = latest_signature
        
        logger.info(f"Loaded {len(self.signatures)} component signatures from storage into memory")
    
    def _scan_and_upsert_signatures(self, components_dir: str, supported_components: list) -> int:
        """Scan components and upsert new signatures to persistent storage."""
        import ast
        
        generated_count = 0
        scanned_files = 0
        found_classes = 0
        
        logger.info(f"Starting comprehensive component scan of {components_dir}")
        
        for root, dirs, files in os.walk(components_dir):
            # Skip __pycache__, .git, and other non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('__pycache__') and not d.startswith('.')]
            
            for file in files:
                if not file.endswith('.py') or file.startswith('__'):
                    continue
                
                file_path = os.path.join(root, file)
                scanned_files += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # Parse the AST to find ALL classes
                    try:
                        tree = ast.parse(code)
                        
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                found_classes += 1
                                
                                # Check if it looks like a component class
                                if self._is_component_class(node, code):
                                    # Generate component path to match runtime lookup pattern
                                    component_path = self._generate_component_path(node.name)

                                    # Check if component is in the supported list
                                    if node.name in supported_components:
                                        self.sandbox_supported_components.add(component_path)
                                        logger.debug(f"Component {component_path} is in sandbox supported list")
                                    
                                    # Generate signature for the entire file's code
                                    signature = ComponentSignature.create(component_path, code, self.signing_key)
                                    
                                    # Upsert to persistent storage (will skip if signature already exists)
                                    self.storage.upsert_signature(component_path, signature)
                                    generated_count += 1
                                    
                                    # Get relative path for logging
                                    rel_path = os.path.relpath(file_path, components_dir)
                                    sandbox_supported = node.name in supported_components
                                    logger.debug(f"✓ Generated signature for {component_path} from {rel_path} (class={node.name}, sandbox_supported={sandbox_supported})")
                    
                    except SyntaxError as e:
                        # Log syntax errors but continue
                        rel_path = os.path.relpath(file_path, components_dir)
                        logger.debug(f"Skipping {rel_path} due to syntax error: {e}")
                        continue
                        
                except Exception as e:
                    rel_path = os.path.relpath(file_path, components_dir)
                    logger.debug(f"Could not process {rel_path}: {e}")
                    continue
        
        logger.info(f"Scan complete: {scanned_files} files, {found_classes} total classes, {generated_count} signatures processed")
        
        # Log sandbox supported components with details
        if self.sandbox_supported_components:
            from .sandbox_manifest import SANDBOX_MANIFEST
            
            logger.info(f"Components that support sandboxing ({len(self.sandbox_supported_components)}): {sorted(self.sandbox_supported_components)}")
            
            # Log detailed information about each supported component
            for component_config in SANDBOX_MANIFEST:
                component_path = f"component.{component_config.name}"
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
            'Component',      # Standard component suffix
            'Tool',          # Tool components
            'Agent',         # Agent components  
            'Model',         # Model components
            'Embeddings',    # Embedding components
            'Vectorstore',   # Vector store components
            'Loader',        # Document loader components
            'Splitter',      # Text splitter components
            'Retriever',     # Retriever components
            'Memory',        # Memory components
            'Chain',         # Chain components
            'Prompt'         # Prompt components
        ]
        
        for pattern in component_name_patterns:
            if class_name.endswith(pattern):
                return True
        
        # 2. Check inheritance from component base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_patterns = [
                    'Component', 'CustomComponent', 'BaseComponent',
                    'LangChainComponent', 'ProcessingComponent',
                    'InputComponent', 'OutputComponent',
                    'ToolComponent', 'AgentComponent'
                ]
                for pattern in base_patterns:
                    if pattern in base.id:
                        return True
                        
            elif isinstance(base, ast.Attribute):
                # Handle cases like langflow.Component, custom.BaseComponent
                base_attrs = ['Component', 'CustomComponent', 'BaseComponent', 
                             'ToolComponent', 'AgentComponent']
                if base.attr in base_attrs:
                    return True
        
        # 3. Check for component-specific decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if 'component' in decorator.id.lower():
                    return True
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if 'component' in decorator.func.id.lower():
                    return True
        
        # 4. Check for specific attributes that indicate a component
        component_attributes = [
            'display_name', 'description', 'icon', 'inputs', 'outputs',
            'code_class_base_inheritance', '_code_class_base_inheritance'
        ]
        
        for attr_node in node.body:
            if isinstance(attr_node, ast.Assign):
                for target in attr_node.targets:
                    if isinstance(target, ast.Name) and target.id in component_attributes:
                        return True
        
        # 5. Look for component-specific methods
        component_methods = ['build', 'run', 'execute', 'process']
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in component_methods:
                return True
        
        return False
    
    def _get_component_name(self, name: str, file_path: str, code: str) -> str:
        """Get the component's name attribute by trying to instantiate it."""
        try:
            # Try to dynamically import and instantiate the component to get its name attribute
            import importlib.util
            import sys
            import tempfile
            import os
            
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
                    if hasattr(instance, 'name') and instance.name:
                        return instance.name
                except Exception:
                    # If instantiation fails, try to get the name from class attributes
                    if hasattr(component_class, 'name') and component_class.name:
                        return component_class.name
            
        except Exception as e:
            logger.debug(f"Could not get component name for {name} from {file_path}: {e}")
        
        # Fallback to class name
        return name
    
    def _generate_component_path(self, component_name: str) -> str:
        """Generate component path using the component's name attribute."""
        # Use the component's name attribute (e.g., "Agent" for AgentComponent)
        component_path = f"component.{component_name}"
        return component_path
    
    def supports_sandboxing(self, path: str) -> bool:
        """Check if a component supports sandboxing."""
        from .sandbox_manifest import SANDBOX_MANIFEST

        # Extract component name from path (e.g., "component.CustomComponent" -> "CustomComponent")
        component_name = path.split(".")[-1] if "." in path else path

        for component_manifest in SANDBOX_MANIFEST:
            if component_manifest.class_name == component_name or component_manifest.name == component_name:
                return True

        return False
    
    def is_force_sandbox(self, path: str) -> bool:
        """Check if a component is forced to execute in sandbox mode."""
        from .sandbox_manifest import SANDBOX_MANIFEST
        
        # Extract component name from path (e.g., "component.CustomComponent" -> "CustomComponent")
        component_name = path.split(".")[-1] if "." in path else path
        
        # Check if this component has force_sandbox=True in the manifest
        for component_manifest in SANDBOX_MANIFEST:
            if component_manifest.class_name == component_name or component_manifest.name == component_name:
                return component_manifest.force_sandbox
        
        return False
    
    def get_signature(self, path: str) -> Optional[ComponentSignature]:
        """Get signature for a component path."""
        return self.signatures.get(path)

    def verify_component_signature(self, path: str, code: str) -> bool:
        """
        Verify code against any historical signature for the component.
        This prevents breaking existing flows when components are updated.
        """
        # Get all signatures for this component (including historical ones)
        all_signatures = self.storage.get_signatures(path)

        if not all_signatures:
            return False
        
        # Try to verify against any signature
        for signature in all_signatures:
            try:
                if signature.verify(code, self.signing_key):
                    return True
            except Exception as e:
                logger.debug(f"Verification error for {path} with signature from {signature.timestamp}: {e}")
                continue
        return False