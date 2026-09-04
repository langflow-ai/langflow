"""lfx-empiriolabs: EmpirioLabs bundle.

Distribution unit ``lfx-empiriolabs``.  At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py`` and registers the
bundle's components under the namespaced IDs
``ext:empiriolabs:EmpirioLabsModelComponent@official`` and
``ext:empiriolabs:EmpirioLabsImageGenerationComponent@official``.
"""

from lfx_empiriolabs.components.empiriolabs.empiriolabs import EmpirioLabsModelComponent
from lfx_empiriolabs.components.empiriolabs.empiriolabs_image_generation import EmpirioLabsImageGenerationComponent

__all__ = ["EmpirioLabsImageGenerationComponent", "EmpirioLabsModelComponent"]
