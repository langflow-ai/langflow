from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .agentql_composio import ComposioAgentQLAPIComponent
    from .agiled_composio import ComposioAgiledAPIComponent
    from .airtable_composio import ComposioAirtableAPIComponent
    from .asana_composio import ComposioAsanaAPIComponent
    from .attio_composio import ComposioAttioAPIComponent
    from .bolna_composio import ComposioBolnaAPIComponent
    from .brandfetch_composio import ComposioBrandfetchAPIComponent
    from .brightdata_composio import ComposioBrightdataAPIComponent
    from .calendly_composio import ComposioCalendlyAPIComponent
    from .capsulecrm_composio import ComposioCapsuleCRMAPIComponent
    from .canvas_composio import ComposioCanvaasAPIComponent
    from .composio_api import ComposioAPIComponent
    from .contentful_composio import ComposioContentfulAPIComponent
    from .discord_composio import ComposioDiscordAPIComponent
    from .digicert_composio import ComposioDigicertAPIComponent
    from .figma_composio import ComposioFigmaAPIComponent
    from .github_composio import ComposioGitHubAPIComponent
    from .jira_composio import ComposioJiraAPIComponent
    from .gmail_composio import ComposioGmailAPIComponent
    from .googlecalendar_composio import ComposioGoogleCalendarAPIComponent
    from .googledocs_composio import ComposioGoogleDocsAPIComponent
    from .googlemeet_composio import ComposioGooglemeetAPIComponent
    from .googlesheets_composio import ComposioGoogleSheetsAPIComponent
    from .googletasks_composio import ComposioGoogleTasksAPIComponent
    from .klaviyo_composio import ComposioKlaviyoAPIComponent
    from .linear_composio import ComposioLinearAPIComponent
    from .miro_composio import ComposioMiroAPIComponent
    from .notion_composio import ComposioNotionAPIComponent
    from .onedrive_composio import ComposioOneDriveAPIComponent
    from .outlook_composio import ComposioOutlookAPIComponent
    from .reddit_composio import ComposioRedditAPIComponent
    from .slack_composio import ComposioSlackAPIComponent
    from .slackbot_composio import ComposioSlackbotAPIComponent
    from .supabase_composio import ComposioSupabaseAPIComponent
    from .timelinesai_composio import ComposioTimelinesaiAPIComponent
    from .todoist_composio import ComposioTodoistAPIComponent
    from .wrike_composio import ComposioWrikeAPIComponent
    from .youtube_composio import ComposioYoutubeAPIComponent

_dynamic_imports = {
    "ComposioAPIComponent": "composio_api",
    "ComposioAgentQLAPIComponent": "agentql_composio",
    "ComposioAgiledAPIComponent": "agiled_composio",
    "ComposioAirtableAPIComponent": "airtable_composio",
    "ComposioAsanaAPIComponent": "asana_composio",
    "ComposioAttioAPIComponent": "attio_composio",
    "ComposioBolnaAPIComponent": "bolna_composio",
    "ComposioBrandfetchAPIComponent": "brandfetch_composio",
    "ComposioBrightdataAPIComponent": "brightdata_composio",
    "ComposioCalendlyAPIComponent": "calendly_composio",
    "ComposioCapsuleCRMAPIComponent": "capsulecrm_composio",
    "ComposioCanvaasAPIComponent": "canvaas_composio",
    "ComposioContentfulAPIComponent": "contentful_composio",
    "ComposioDiscordAPIComponent": "discord_composio",
    "ComposioDigicertAPIComponent": "digicert_composio",
    "ComposioFigmaAPIComponent": "figma_composio",
    "ComposioGitHubAPIComponent": "github_composio",
    "ComposioGmailAPIComponent": "gmail_composio",
    "ComposioGoogleCalendarAPIComponent": "googlecalendar_composio",
    "ComposioGoogleDocsAPIComponent": "googledocs_composio",
    "ComposioGoogleSheetsAPIComponent": "googlesheets_composio",
    "ComposioGoogleTasksAPIComponent": "googletasks_composio",
    "ComposioGooglemeetAPIComponent": "googlemeet_composio",
    "ComposioJiraAPIComponent": "jira_composio",
    "ComposioKlaviyoAPIComponent": "klaviyo_composio",
    "ComposioLinearAPIComponent": "linear_composio",
    "ComposioMiroAPIComponent": "miro_composio",
    "ComposioNotionAPIComponent": "notion_composio",
    "ComposioOneDriveAPIComponent": "onedrive_composio",
    "ComposioOutlookAPIComponent": "outlook_composio",
    "ComposioRedditAPIComponent": "reddit_composio",
    "ComposioSlackAPIComponent": "slack_composio",
    "ComposioSlackbotAPIComponent": "slackbot_composio",
    "ComposioSupabaseAPIComponent": "supabase_composio",
    "ComposioTimelinesaiAPIComponent": "timelinesai_composio",
    "ComposioTodoistAPIComponent": "todoist_composio",
    "ComposioWrikeAPIComponent": "wrike_composio",
    "ComposioYoutubeAPIComponent": "youtube_composio",
}

# Always expose all components - individual failures will be handled on import
__all__ = [
    "ComposioAPIComponent",
    "ComposioAgentQLAPIComponent",
    "ComposioAgiledAPIComponent",
    "ComposioAirtableAPIComponent",
    "ComposioAsanaAPIComponent",
    "ComposioAttioAPIComponent",
    "ComposioBolnaAPIComponent",
    "ComposioBrandfetchAPIComponent",
    "ComposioBrightdataAPIComponent",
    "ComposioCalendlyAPIComponent",
    "ComposioCapsuleCRMAPIComponent",
    "ComposioCanvaasAPIComponent",
    "ComposioContentfulAPIComponent",
    "ComposioDiscordAPIComponent",
    "ComposioDigicertAPIComponent",
    "ComposioFigmaAPIComponent",
    "ComposioGitHubAPIComponent",
    "ComposioGmailAPIComponent",
    "ComposioGoogleCalendarAPIComponent",
    "ComposioGoogleDocsAPIComponent",
    "ComposioGoogleSheetsAPIComponent",
    "ComposioGoogleTasksAPIComponent",
    "ComposioGooglemeetAPIComponent",
    "ComposioJiraAPIComponent",
    "ComposioKlaviyoAPIComponent",
    "ComposioLinearAPIComponent",
    "ComposioMiroAPIComponent",
    "ComposioNotionAPIComponent",
    "ComposioOneDriveAPIComponent",
    "ComposioOutlookAPIComponent",
    "ComposioRedditAPIComponent",
    "ComposioSlackAPIComponent",
    "ComposioSlackbotAPIComponent",
    "ComposioSupabaseAPIComponent",
    "ComposioTimelinesaiAPIComponent",
    "ComposioTodoistAPIComponent",
    "ComposioWrikeAPIComponent",
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
