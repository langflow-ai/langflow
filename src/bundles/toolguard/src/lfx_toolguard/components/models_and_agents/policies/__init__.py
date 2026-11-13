# Supporting utilities for the ToolGuard Policies extension.

import sys

# The pinned LiteLLM 1.103 line imports these names when ToolGuard loads its
# build-time API. Python 3.15 removed the aliases for the same regex modules.
if sys.version_info >= (3, 15):
    from re import _constants, _parser

    sys.modules.setdefault("sre_constants", _constants)
    sys.modules.setdefault("sre_parse", _parser)


__all__ = []
