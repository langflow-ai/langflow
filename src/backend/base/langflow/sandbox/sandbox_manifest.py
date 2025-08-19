"""
List of components that have been tested and verified to work correctly in the sandbox.

This list is manually maintained. When a component has been thoroughly tested
in the sandbox environment, add its configuration here.
"""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class SandboxComponentManifest:
    """Configuration for a component that supports sandboxing."""
    class_name: str             # The actual Python class name (e.g., "APIRequestComponent")
    name: str                   # The components name property (e.g., "APIRequest")
    notes: str                  # Explanation of sandboxing requirements/testing status
    force_sandbox: bool = False # If true the component will always execute in the sandbox

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "class_name": self.class_name,
            "name": self.name,
            "force_sandbox": self.force_sandbox,
            "notes": self.notes
        }


# List of components that have been tested and verified to work in sandbox
SANDBOX_MANIFEST: List[SandboxComponentManifest] = [
    SandboxComponentManifest(
        name="APIRequest",
        class_name="APIRequestComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="CurrentDate",
        class_name="CurrentDateComponent",
        notes="Tested and works as expected."
    ),
    
    SandboxComponentManifest(
        name="CustomComponent",
        class_name="CustomComponent",
        force_sandbox=True,
        notes="Base custom component template. Tested with basic input/output operations, "
              "file handling, and async operations. Safe for user-defined logic although may"
              "encounter side-effects depending on imports used."
    ),

    SandboxComponentManifest(
        name="PythonREPLComponent",
        class_name="PythonREPLComponent",
        notes="Tested and works as expected."
    ),
    
    SandboxComponentManifest(
        name="TypeConverterComponent",
        class_name="TypeConverterComponent",
        notes="Tested and works as expected."
    ),
]

def get_supported_component_class_names() -> List[str]:
    """Get list of supported component class names."""
    return [component.class_name for component in SANDBOX_MANIFEST]
