"""lfx-getyoutubetranscript: GetYouTubeTranscript bundle.

This package is the distribution unit ``lfx-getyoutubetranscript``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``GetYouTubeTranscriptComponent`` under the
namespaced ID ``ext:getyoutubetranscript:GetYouTubeTranscriptComponent@official``.

GetYouTubeTranscript (https://getyoutubetranscript.com) is a YouTube transcript
API; the component calls it directly with ``httpx`` and needs only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_getyoutubetranscript.components.getyoutubetranscript.getyoutubetranscript import (
    GetYouTubeTranscriptComponent,
)

__all__ = ["GetYouTubeTranscriptComponent"]
