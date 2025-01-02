from pydantic import BaseModel


class WebhookJobData(BaseModel):
    """Data structure for webhook job notifications."""

    id: str
    status: str
    result: dict | None
    name: str | None
    flow_id: str | None
    user_id: str | None
