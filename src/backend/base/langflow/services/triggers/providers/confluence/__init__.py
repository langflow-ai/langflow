"""Server runtime owned by the distinct Confluence integration bundle."""

from langflow.services.triggers.providers.confluence.collector import collect, normalize_config, prepare
from langflow.services.triggers.providers.confluence.oauth import OAUTH
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider

PROVIDER = TriggerProvider(
    provider_id="confluence",
    bundle="confluence_integrations",
    kinds=tuple(
        TriggerKind(
            kind=kind,
            component=component,
            display_name=name,
            config_fields=("connection", "space_id", "delivery_mode"),
            required_scopes=("read:page:confluence", "offline_access"),
            poll_mechanism="confluence.page.poll",
        )
        for kind, component, name in (
            ("confluence.page_created", "ConfluenceOnPageCreatedTriggerComponent", "Confluence On Page Created"),
            ("confluence.page_updated", "ConfluenceOnPageUpdatedTriggerComponent", "Confluence On Page Updated"),
        )
    ),
    normalize_config=normalize_config,
    collect=collect,
    prepare=prepare,
    oauth=OAUTH,
    api_origins=("https://api.atlassian.com",),
)
