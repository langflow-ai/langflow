"""lfx-paddle: PaddleOCR bundle.

Distribution unit ``lfx-paddle``.  At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py`` and registers the
bundle's component under the namespaced ID
``ext:paddle:PaddleOCRComponent@official``.
"""

from lfx_paddle.components.paddle.paddleocr import PaddleOCRComponent

__all__ = ["PaddleOCRComponent"]
