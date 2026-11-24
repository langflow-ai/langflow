from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleclassroomAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Classroom"
    icon = "Classroom"
    documentation: str = "https://docs.composio.dev"
    app_name = "GOOGLE_CLASSROOM"

    def set_default_tools(self):
        """Set the default tools for Google Classroom component."""
