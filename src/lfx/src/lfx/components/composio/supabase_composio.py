from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSupabaseAPIComponent(ComposioBaseComponent):
    component_id: str = "bd07f2c3-7c19-4e9e-ab78-6375a3167a54"
    display_name: str = "Supabase"
    icon = "Supabase"
    documentation: str = "https://docs.composio.dev"
    app_name = "supabase"

    def set_default_tools(self):
        """Set the default tools for Supabase component."""
