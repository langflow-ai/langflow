"""lfx-uploadpost: Upload-Post social publishing bundle.

This package is the distribution unit ``lfx-uploadpost``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers the components under namespaced IDs such as
``ext:uploadpost:UploadPostVideoComponent@official``.

Upload-Post (https://upload-post.com) publishes one video, photo set or text
post to TikTok, Instagram, YouTube, LinkedIn, Facebook, X, Threads, Pinterest
and Bluesky in a single call; the components call its REST API directly with
``httpx`` and need only a user-supplied API key, so the bundle carries no
vendor SDK dependency.
"""

from lfx_uploadpost.components.uploadpost import (
    UploadPostPhotosComponent,
    UploadPostStatusComponent,
    UploadPostTextComponent,
    UploadPostVideoComponent,
)

__all__ = [
    "UploadPostPhotosComponent",
    "UploadPostStatusComponent",
    "UploadPostTextComponent",
    "UploadPostVideoComponent",
]
