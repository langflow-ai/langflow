from lfx.custom.custom_component.component import *  # noqa: F403

# Re-export everything from lfx.custom.custom_component.component


# For backwards compatibility
def _get_component_toolkit():
    global _component_toolkit
    if _component_toolkit is None:
        from lfx.base.tools.component_tool import ComponentToolkit

        _component_toolkit = ComponentToolkit
    return _component_toolkit


_component_toolkit = None
