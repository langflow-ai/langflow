"""Shared base infrastructure for the huggingface bundle.

Houses the mixin(s) every component in this bundle inherits from --
pre-extraction this lived at ``lfx.base.huggingface``.  Moved into the
bundle (not kept in lfx) because it is huggingface-specific and only ever
imported by the huggingface components.
"""

from lfx_huggingface.base.model_bridge import LangChainHFModel

__all__ = [
    "LangChainHFModel",
]
