import asyncio
from typing import Any, Protocol


class GetCache(Protocol):
    async def __call__(self, key: str, lock: asyncio.Lock | None = None) -> Any: ...


class SetCache(Protocol):
    async def __call__(self, key: str, data: Any, lock: asyncio.Lock | None = None) -> bool: ...
