from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioMem0APIComponent(ComposioBaseComponent):
    component_id: str = "41cb6db6-2235-41ae-9020-8ef06d4e7b0b"
    display_name: str = "Mem0"
    icon = "Mem0Composio"
    documentation: str = "https://docs.composio.dev"
    app_name = "mem0"

    def set_default_tools(self):
        """Set the default tools for Mem0 component."""
