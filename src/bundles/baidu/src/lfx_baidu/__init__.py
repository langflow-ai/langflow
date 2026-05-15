"""lfx-baidu: Baidu bundle.

Distribution unit ``lfx-baidu``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:baidu:<Class>@official``.
"""

from lfx_baidu.components.baidu.baidu_qianfan_chat import QianfanChatEndpointComponent

__all__ = [
    "QianfanChatEndpointComponent",
]
