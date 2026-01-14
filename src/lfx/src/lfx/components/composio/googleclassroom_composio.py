from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleclassroomAPIComponent(ComposioBaseComponent):
    component_id: str = "2cabdb24-c721-4f24-8882-b9417ddd550f"
    display_name: str = "Google Classroom"
    icon = "Classroom"
    documentation: str = "https://docs.composio.dev"
    app_name = "GOOGLE_CLASSROOM"

    def set_default_tools(self):
        """Set the default tools for Google Classroom component."""
