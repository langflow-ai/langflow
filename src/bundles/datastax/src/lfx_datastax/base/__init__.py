"""Shared base infrastructure for the datastax bundle.

Houses the ``AstraDBBaseComponent`` mixin that all astra-* components
inherit -- pre-extraction this lived at ``lfx.base.datastax``.  Moved
into the bundle (not kept in lfx) because it is datastax-specific and
only ever imported by the datastax components.
"""

from lfx_datastax.base.astradb_base import AstraDBBaseComponent

__all__ = ["AstraDBBaseComponent"]
