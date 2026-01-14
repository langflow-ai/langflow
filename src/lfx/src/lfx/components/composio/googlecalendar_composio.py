from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleCalendarAPIComponent(ComposioBaseComponent):
    component_id: str = "8e908364-dc1a-48fe-9d2b-9d1af0293773"
    display_name: str = "GoogleCalendar"
    icon = "Googlecalendar"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlecalendar"

    def set_default_tools(self):
        """Set the default tools for Google Calendar component."""
