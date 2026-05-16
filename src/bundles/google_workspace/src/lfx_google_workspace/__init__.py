"""lfx-google-workspace: Google Workspace bundle.

Distribution unit ``lfx-google-workspace``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:google_workspace:<Class>@official``.

Part of the Google split: 9 components from the in-tree ``google/``
directory were partitioned across 4 lfx-google-* bundles by audience
(GenAI / Workspace / BigQuery / Search).
"""

from lfx_google_workspace.components.google_workspace.gmail import GmailLoaderComponent
from lfx_google_workspace.components.google_workspace.google_drive import GoogleDriveComponent
from lfx_google_workspace.components.google_workspace.google_drive_search import GoogleDriveSearchComponent
from lfx_google_workspace.components.google_workspace.google_oauth_token import GoogleOAuthToken

__all__ = [
    "GmailLoaderComponent",
    "GoogleDriveComponent",
    "GoogleDriveSearchComponent",
    "GoogleOAuthToken",
]
