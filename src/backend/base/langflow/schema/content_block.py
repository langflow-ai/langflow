"""Re-export shim.

ContentBlock and ContentType now live in content_types.py alongside the
rest of the discriminated union.
"""

from .content_types import ContentBlock, ContentBlockDict, ContentType

__all__ = ["ContentBlock", "ContentBlockDict", "ContentType"]
