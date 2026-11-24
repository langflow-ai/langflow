"""Compatibility shim for the Policies component moved to ``lfx-toolguard``."""

try:
    from lfx_toolguard.components.models_and_agents.policies_component import PoliciesComponent
except ModuleNotFoundError as exc:
    if exc.name is not None and exc.name.partition(".")[0] != "lfx_toolguard":
        raise
    msg = (
        "The Policies component moved to the 'lfx-toolguard' distribution. "
        'Install it with `pip install "lfx[toolguard]"`.'
    )
    raise ModuleNotFoundError(msg) from exc

__all__ = ["PoliciesComponent"]
