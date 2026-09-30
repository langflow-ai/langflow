"""Component re-exports for the ``empiriolabs`` bundle.

Saved-flow migration entries that target ``lfx.components.empiriolabs.<Class>``
resolve through this package, so the moved Component classes must be importable
from here by name.
"""

from .empiriolabs import EmpirioLabsModelComponent
from .empiriolabs_image_generation import EmpirioLabsImageGenerationComponent

__all__ = ["EmpirioLabsImageGenerationComponent", "EmpirioLabsModelComponent"]
