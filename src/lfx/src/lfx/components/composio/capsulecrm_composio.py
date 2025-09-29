from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCapsuleCRMAPIComponent(ComposioBaseComponent):
    display_name: str = "CapsuleCRM"
    icon = "CapsuleCRM"
    documentation: str = "https://docs.composio.dev"
    app_name = "capsule_crm"

    def set_default_tools(self):
        """Set the default tools for CapsuleCRM component."""
