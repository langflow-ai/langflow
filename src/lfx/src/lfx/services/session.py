"""Lightweight session implementations for lfx package."""


class NoopSession:
    """No-operation session that implements the database session interface.

    This provides a complete database session API but all operations are no-ops.
    Perfect for testing or when no real database is available.
    """

    class NoopBind:
        class NoopConnect:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            async def run_sync(self, fn, *args, **kwargs):  # noqa: ARG002
                return None

        def connect(self):
            return self.NoopConnect()

    bind = NoopBind()

    async def add(self, *args, **kwargs):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def execute(self, *args, **kwargs):  # noqa: ARG002
        return None

    async def query(self, *args, **kwargs):  # noqa: ARG002
        return []

    async def close(self):
        pass

    async def refresh(self, *args, **kwargs):
        pass

    async def delete(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def get(self, *args, **kwargs):  # noqa: ARG002
        return None

    async def exec(self, *args, **kwargs):  # noqa: ARG002
        class _NoopResult:
            def first(self):
                return None

            def all(self):
                return []

            def one_or_none(self):
                return None

        return _NoopResult()

    @property
    def no_autoflush(self):
        """Context manager that disables autoflush (no-op implementation)."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass
