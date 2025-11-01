from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleTasksAPIComponent(ComposioBaseComponent):
    display_name: str = "GoogleTasks"
    icon = "GoogleTasks"
    documentation: str = "https://docs.composio.dev"
    app_name = "googletasks"
