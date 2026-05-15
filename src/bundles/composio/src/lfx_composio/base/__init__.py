"""Shared base infrastructure for the composio bundle.

Houses the mixin(s) every component in this bundle inherits from --
pre-extraction this lived at ``lfx.base.composio``.  Moved into the
bundle (not kept in lfx) because it is composio-specific and only ever
imported by the composio components.
"""

from lfx_composio.base.composio_base import ComposioBaseComponent

__all__ = [
    "ComposioBaseComponent",
]
