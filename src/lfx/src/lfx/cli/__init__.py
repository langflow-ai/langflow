"""LFX CLI module for serving flows."""

__all__ = ["serve_command"]


def __getattr__(name: str):
    """Lazy import for serve_command."""
    if name == "serve_command":
        from lfx.cli.commands import serve_command

        return serve_command
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
