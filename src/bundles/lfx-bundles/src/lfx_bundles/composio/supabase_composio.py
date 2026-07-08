from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSupabaseAPIComponent(ComposioBaseComponent):
    display_name: str = "Supabase"
    icon = "Supabase"
    documentation: str = "https://docs.composio.dev"
    app_name = "supabase"

    def set_default_tools(self):
        """Set the default tools for Supabase component."""
