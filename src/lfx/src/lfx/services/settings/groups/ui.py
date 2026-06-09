from pydantic import BaseModel

from lfx.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH


class UiSettings(BaseModel):
    """Frontend, auto-save, display limits, and (legacy) Langflow Store integration."""

    auto_saving: bool = True
    """If set to True, Langflow will auto save flows."""
    auto_saving_interval: int = 1000
    """The interval in ms at which Langflow will auto save flows."""

    max_text_length: int = MAX_TEXT_LENGTH
    """Maximum number of characters to store and display in the UI. Responses longer than this
    will be truncated when displayed in the UI. Does not truncate responses between components nor outputs."""
    max_items_length: int = MAX_ITEMS_LENGTH
    """Maximum number of items to store and display in the UI. Lists longer than this
    will be truncated when displayed in the UI. Does not affect data passed between components nor outputs."""

    frontend_timeout: int = 0
    """Timeout for the frontend API calls in seconds."""

    # Langflow Store (legacy)
    store: bool | None = True
    store_url: str | None = "https://api.langflow.store"
    download_webhook_url: str | None = "https://api.langflow.store/flows/trigger/ec611a61-8460-4438-b187-a4f65e5559d4"
    like_webhook_url: str | None = "https://api.langflow.store/flows/trigger/64275852-ec00-45c1-984e-3bff814732da"
