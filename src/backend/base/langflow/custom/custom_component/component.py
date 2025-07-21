from lfx.custom.custom_component.component import *  # noqa: F403

# Re-export everything from lfx.custom.custom_component.component


# For backwards compatibility
def _get_component_toolkit():
    from lfx.custom.tools import ComponentToolkit

    return ComponentToolkit
