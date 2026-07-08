"""Component re-exports for the ``paddle`` bundle.

Saved-flow migration entries that target ``lfx.components.paddle.<Class>``
resolve through this package, so the moved Component class(es) must be
importable from here by name.
"""

from .paddleocr import PaddleOCRComponent

__all__ = ["PaddleOCRComponent"]
