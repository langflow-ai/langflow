from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTodoistAPIComponent(ComposioBaseComponent):
    component_id: str = "d5127aa3-a57b-43e0-9dc3-83dd213dbb18"
    display_name: str = "Todoist"
    icon = "Todoist"
    documentation: str = "https://docs.composio.dev"
    app_name = "todoist"

    def set_default_tools(self):
        """Set the default tools for Todoist component."""
