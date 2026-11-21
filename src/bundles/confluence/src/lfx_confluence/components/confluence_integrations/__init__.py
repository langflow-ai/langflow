"""Stable Confluence integration component identities."""

from .actions import (
    ConfluenceCreatePageComponent,
    ConfluenceReadPageComponent,
    ConfluenceSearchPagesComponent,
    ConfluenceUpdatePageComponent,
)
from .triggers import ConfluenceOnPageCreatedTriggerComponent, ConfluenceOnPageUpdatedTriggerComponent

__all__ = [
    "ConfluenceCreatePageComponent",
    "ConfluenceOnPageCreatedTriggerComponent",
    "ConfluenceOnPageUpdatedTriggerComponent",
    "ConfluenceReadPageComponent",
    "ConfluenceSearchPagesComponent",
    "ConfluenceUpdatePageComponent",
]
