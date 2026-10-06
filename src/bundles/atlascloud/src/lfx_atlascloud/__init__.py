"""lfx-atlascloud: Atlas Cloud bundle.

Distribution unit ``lfx-atlascloud``.  At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py`` and registers the
bundle's component under the namespaced ID
``ext:atlascloud:AtlasCloudModelComponent@official``.
"""

from lfx_atlascloud.components.atlascloud.atlascloud import AtlasCloudModelComponent

__all__ = ["AtlasCloudModelComponent"]
