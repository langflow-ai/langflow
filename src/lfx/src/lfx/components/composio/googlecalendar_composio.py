from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleCalendarAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Calendar"
    icon = "Googlecalendar"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlecalendar"

    def set_default_tools(self):
        """Set the default tools for Google Calendar component."""
