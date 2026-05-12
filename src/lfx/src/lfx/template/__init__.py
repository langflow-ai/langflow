from __future__ import annotations

__all__ = [
    "Input",
    "Output",
]


def __getattr__(name: str):
    if name in {"Input", "Output"}:
        from lfx.template.field.base import Input, Output

        globals()["Input"] = Input
        globals()["Output"] = Output
        return globals()[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
