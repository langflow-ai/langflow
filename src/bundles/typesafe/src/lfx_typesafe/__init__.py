"""lfx-typesafe: TypeSafe System One bundle.

Distribution unit ``lfx-typesafe``. At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py`` and registers the
bundle's components under the namespaced IDs
``ext:typesafe:<Class>@official``.
"""

from lfx_typesafe.components.typesafe.typesafe_system_one import TypeSafeSystemOneComponent

__all__ = ["TypeSafeSystemOneComponent"]
