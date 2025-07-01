from base.langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleTasksAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Tasks"
    description: str = "GoogleTasks API"
    icon = "GoogleTasks"
    documentation: str = "https://docs.composio.dev"
    app_name = "googletasks"



