from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .apollo_composio import ComposioApolloAPIComponent
    from .airtable_composio import ComposioAirtableAPIComponent
    from .bitbucket_composio import ComposioBitbucketAPIComponent
    from .asana_composio import ComposioAsanaAPIComponent
    from .attio_composio import ComposioAttioAPIComponent
    from .canva_composio import ComposioCanvaAPIComponent
    from .calendly_composio import ComposioCalendlyAPIComponent
    from .composio_api import ComposioAPIComponent
    from .contentful_composio import ComposioContentfulAPIComponent
    from .coda_composio import ComposioCodaAPIComponent
    from .discord_composio import ComposioDiscordAPIComponent
    from .elevenlabs_composio import ComposioElevenLabsAPIComponent
    from .exa_composio import ComposioExaAPIComponent
    from .firecrawl_composio import ComposioFirecrawlAPIComponent
    from .fireflies_composio import ComposioFirefliesAPIComponent
    from .figma_composio import ComposioFigmaAPIComponent
    from .github_composio import ComposioGitHubAPIComponent
    from .gmail_composio import ComposioGmailAPIComponent
    from .googlebigquery_composio import ComposioGoogleBigQueryAPIComponent
    from .googlecalendar_composio import ComposioGoogleCalendarAPIComponent
    from .googledocs_composio import ComposioGoogleDocsAPIComponent
    from .googlemeet_composio import ComposioGooglemeetAPIComponent
    from .googlesheets_composio import ComposioGoogleSheetsAPIComponent
    from .googletasks_composio import ComposioGoogleTasksAPIComponent
    from .heygen_composio import ComposioHeygenAPIComponent
    from .klaviyo_composio import ComposioKlaviyoAPIComponent
    from .linear_composio import ComposioLinearAPIComponent
    from .mem0_composio import ComposioMem0APIComponent
    from .miro_composio import ComposioMiroAPIComponent
    from .notion_composio import ComposioNotionAPIComponent
    from .onedrive_composio import ComposioOneDriveAPIComponent
    from .outlook_composio import ComposioOutlookAPIComponent
    from .peopledatalabs_composio import ComposioPeopleDataLabsAPIComponent
    from .perplexityai_composio import ComposioPerplexityAIAPIComponent
    from .reddit_composio import ComposioRedditAPIComponent
    from .serpapi_composio import ComposioSerpAPIComponent
    from .slack_composio import ComposioSlackAPIComponent
    from .slackbot_composio import ComposioSlackbotAPIComponent
    from .snowflake_composio import ComposioSnowflakeAPIComponent
    from .supabase_composio import ComposioSupabaseAPIComponent
    from .tavily_composio import ComposioTavilyAPIComponent
    from .todoist_composio import ComposioTodoistAPIComponent
    from .wrike_composio import ComposioWrikeAPIComponent
    from .youtube_composio import ComposioYoutubeAPIComponent


_dynamic_imports = {
    "ComposioAPIComponent": "composio_api",
    "ComposioApolloAPIComponent": "apollo_composio",
    "ComposioGitHubAPIComponent": "github_composio",
    "ComposioGmailAPIComponent": "gmail_composio",
    "ComposioBitbucketAPIComponent": "bitbucket_composio",
    "ComposioGoogleCalendarAPIComponent": "googlecalendar_composio",
    "ComposioCanvaAPIComponent": "canva_composio",
    "ComposioCodaAPIComponent": "coda_composio",
    "ComposioElevenLabsAPIComponent": "elevenlabs_composio",
    "ComposioExaAPIComponent": "exa_composio",
    "ComposioFirecrawlAPIComponent": "firecrawl_composio",
    "ComposioFirefliesAPIComponent": "fireflies_composio",
    "ComposioGooglemeetAPIComponent": "googlemeet_composio",
    "ComposioGoogleBigQueryAPIComponent": "googlebigquery_composio",
    "ComposioOutlookAPIComponent": "outlook_composio",
    "ComposioHeygenAPIComponent": "heygen_composio",
    "ComposioSlackAPIComponent": "slack_composio",
    "ComposioGoogleTasksAPIComponent": "googletasks_composio",
    "ComposioLinearAPIComponent": "linear_composio",
    "ComposioRedditAPIComponent": "reddit_composio",
    "ComposioMem0APIComponent": "mem0_composio",
    "ComposioSlackbotAPIComponent": "slackbot_composio",
    "ComposioPeopleDataLabsAPIComponent": "peopledatalabs_composio",
    "ComposioPerplexityAIAPIComponent": "perplexityai_composio",
    "ComposioSupabaseAPIComponent": "supabase_composio",
    "ComposioSerpAPIComponent": "serpapi_composio",
    "ComposioSnowflakeAPIComponent": "snowflake_composio",
    "ComposioTodoistAPIComponent": "todoist_composio",
    "ComposioTavilyAPIComponent": "tavily_composio",
    "ComposioYoutubeAPIComponent": "youtube_composio",
    "ComposioGoogleDocsAPIComponent": "googledocs_composio",
    "ComposioGoogleSheetsAPIComponent": "googlesheets_composio",
    "ComposioKlaviyoAPIComponent": "klaviyo_composio",
    "ComposioNotionAPIComponent": "notion_composio",
    "ComposioOneDriveAPIComponent": "onedrive_composio",
    "ComposioAirtableAPIComponent": "airtable_composio",
    "ComposioAsanaAPIComponent": "asana_composio",
    "ComposioAttioAPIComponent": "attio_composio",
    "ComposioCalendlyAPIComponent": "calendly_composio",
    "ComposioContentfulAPIComponent": "contentful_composio",
    "ComposioDiscordAPIComponent": "discord_composio",
    "ComposioFigmaAPIComponent": "figma_composio",
    "ComposioMiroAPIComponent": "miro_composio",
    "ComposioWrikeAPIComponent": "wrike_composio",
}

# Always expose all components - individual failures will be handled on import
__all__ = [
    "ComposioAPIComponent",
    "ComposioApolloAPIComponent",
    "ComposioAirtableAPIComponent",
    "ComposioBitbucketAPIComponent",
    "ComposioAsanaAPIComponent",
    "ComposioAttioAPIComponent",
    "ComposioCanvaAPIComponent",
    "ComposioCalendlyAPIComponent",
    "ComposioContentfulAPIComponent",
    "ComposioCodaAPIComponent",
    "ComposioDiscordAPIComponent",
    "ComposioElevenLabsAPIComponent",
    "ComposioExaAPIComponent",
    "ComposioFirecrawlAPIComponent",
    "ComposioFirefliesAPIComponent",
    "ComposioFigmaAPIComponent",
    "ComposioGitHubAPIComponent",
    "ComposioGmailAPIComponent",
    "ComposioGoogleBigQueryAPIComponent",
    "ComposioGoogleCalendarAPIComponent",
    "ComposioGoogleDocsAPIComponent",
    "ComposioGoogleSheetsAPIComponent",
    "ComposioGoogleTasksAPIComponent",
    "ComposioGooglemeetAPIComponent",
    "ComposioHeygenAPIComponent",
    "ComposioKlaviyoAPIComponent",
    "ComposioLinearAPIComponent",
    "ComposioMem0APIComponent",
    "ComposioMiroAPIComponent",
    "ComposioNotionAPIComponent",
    "ComposioOneDriveAPIComponent",
    "ComposioOutlookAPIComponent",
    "ComposioPeopleDataLabsAPIComponent",
    "ComposioPerplexityAIAPIComponent",
    "ComposioRedditAPIComponent",
    "ComposioSerpAPIComponent",
    "ComposioSlackAPIComponent",
    "ComposioSlackbotAPIComponent",
    "ComposioSnowflakeAPIComponent",
    "ComposioSupabaseAPIComponent",
    "ComposioTavilyAPIComponent",
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
