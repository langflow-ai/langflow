from lfx.services.deps import get_settings_service

DEFAULT_USER_AGENT = "Langflow"


def get_user_agent():
    """Get user agent with fallback."""
    try:
        settings_service = get_settings_service()
        if (
            settings_service
            and hasattr(settings_service, "settings")
            and hasattr(settings_service.settings, "user_agent")
        ):
            return settings_service.settings.user_agent
    except (AttributeError, TypeError):
        pass
    return DEFAULT_USER_AGENT
