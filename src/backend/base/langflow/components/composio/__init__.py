from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .composio_api import ComposioAPIComponent
    from .github_composio import ComposioGitHubAPIComponent
    from .gmail_composio import ComposioGmailAPIComponent
    from .googlecalendar_composio import ComposioGoogleCalendarAPIComponent
    from .googlemeet_composio import ComposioGooglemeetAPIComponent
    from .googletasks_composio import ComposioGoogleTasksAPIComponent
    from .linear_composio import ComposioLinearAPIComponent
    from .outlook_composio import ComposioOutlookAPIComponent
    from .reddit_composio import ComposioRedditAPIComponent
    from .slack_composio import ComposioSlackAPIComponent
    from .slackbot_composio import ComposioSlackbotAPIComponent
    from .supabase_composio import ComposioSupabaseAPIComponent
    from .todoist_composio import ComposioTodoistAPIComponent
    from .youtube_composio import ComposioYoutubeAPIComponent

_dynamic_imports = {
    "ComposioAPIComponent": "composio_api",
    "ComposioGitHubAPIComponent": "github_composio",
    "ComposioGmailAPIComponent": "gmail_composio",
    "ComposioGoogleCalendarAPIComponent": "googlecalendar_composio",
    "ComposioGooglemeetAPIComponent": "googlemeet_composio",
    "ComposioOutlookAPIComponent": "outlook_composio",
    "ComposioSlackAPIComponent": "slack_composio",
    "ComposioGoogleTasksAPIComponent": "googletasks_composio",
    "ComposioLinearAPIComponent": "linear_composio",
    "ComposioRedditAPIComponent": "reddit_composio",
    "ComposioSlackbotAPIComponent": "slackbot_composio",
    "ComposioSupabaseAPIComponent": "supabase_composio",
    "ComposioTodoistAPIComponent": "todoist_composio",
    "ComposioYoutubeAPIComponent": "youtube_composio",
}

__all__ = [
    "ComposioAPIComponent",
    "ComposioGitHubAPIComponent",
    "ComposioGmailAPIComponent",
    "ComposioGoogleCalendarAPIComponent",
    "ComposioGoogleTasksAPIComponent",
    "ComposioGooglemeetAPIComponent",
    "ComposioLinearAPIComponent",
    "ComposioOutlookAPIComponent",
    "ComposioRedditAPIComponent",
    "ComposioSlackAPIComponent",
    "ComposioSlackbotAPIComponent",
    "ComposioSupabaseAPIComponent",
    "ComposioTodoistAPIComponent",
    "ComposioYoutubeAPIComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import composio components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
