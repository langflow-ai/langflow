"""List of components that have been tested and verified to work correctly in the sandbox.

This list is manually maintained. When a component has been thoroughly tested
in the sandbox environment, add its configuration here.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SandboxComponentManifest:
    """Configuration for a component that supports sandboxing."""
    class_name: str             # The actual Python class name (e.g., "APIRequestComponent")
    name: str                   # The components name property (e.g., "APIRequest")
    notes: str                  # Explanation of sandboxing requirements/testing status
    force_sandbox: bool = False # If true the component will always execute in the sandbox

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "class_name": self.class_name,
            "name": self.name,
            "force_sandbox": self.force_sandbox,
            "notes": self.notes
        }


# List of components that have been tested and verified to work in sandbox
SANDBOX_MANIFEST: list[SandboxComponentManifest] = [

    SandboxComponentManifest(
        name="APIRequest",
        class_name="APIRequestComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="ChatInput",
        class_name="ChatInput",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="ChatOutput",
        class_name="ChatOutput",
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
        notes="Tested and works as expected."
              "May encounter side-effects depending on imports used."
    ),

    SandboxComponentManifest(
        name="DataOperations",
        class_name="DataOperationsComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="ParserComponent",
        class_name="ParserComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="PythonREPLComponent",
        class_name="PythonREPLComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="TextInput",
        class_name="TextInputComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="TextOutput",
        class_name="TextOutputComponent",
        notes="Tested and works as expected."
    ),

    SandboxComponentManifest(
        name="TypeConverterComponent",
        class_name="TypeConverterComponent",
        notes="Tested and works as expected."
    ),
]

def get_supported_component_class_names() -> list[str]:
    """Get list of supported component class names."""
    return [component.class_name for component in SANDBOX_MANIFEST]
