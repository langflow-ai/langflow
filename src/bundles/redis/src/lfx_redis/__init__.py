"""lfx-redis: Redis bundle.

Distribution unit ``lfx-redis``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:redis:<Class>@official``.
"""

from lfx_redis.components.redis.redis import RedisVectorStoreComponent
from lfx_redis.components.redis.redis_chat import RedisIndexChatMemory

__all__ = [
    "RedisIndexChatMemory",
    "RedisVectorStoreComponent",
]
