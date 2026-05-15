"""Shared base infrastructure for the langwatch bundle.

Houses the mixin(s) every component in this bundle inherits from --
pre-extraction this lived at ``lfx.base.langwatch``.  Moved into the
bundle (not kept in lfx) because it is langwatch-specific and only ever
imported by the langwatch components.
"""

__all__: list[str] = []
