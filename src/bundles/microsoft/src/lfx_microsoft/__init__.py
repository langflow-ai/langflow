"""Microsoft 365 and Teams components backed by delegated Microsoft Graph permissions."""

from lfx_microsoft.components.microsoft import (
    OutlookCalendarCreateComponent,
    OutlookCalendarListComponent,
    OutlookSearchComponent,
    OutlookSendComponent,
    SharePointFetchComponent,
    SharePointListComponent,
    TeamsChannelPostComponent,
    TeamsChatPostComponent,
)
from lfx_microsoft.graph import GraphClient

__all__ = [
    "GraphClient",
    "OutlookCalendarCreateComponent",
    "OutlookCalendarListComponent",
    "OutlookSearchComponent",
    "OutlookSendComponent",
    "SharePointFetchComponent",
    "SharePointListComponent",
    "TeamsChannelPostComponent",
    "TeamsChatPostComponent",
]
