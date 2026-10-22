"""Installed Salesforce record source descriptor."""

from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.providers.salesforce.collector import collect, normalize_config, prepare
from langflow.services.triggers.providers.salesforce.oauth import OAUTH

PROVIDER = TriggerProvider(
    provider_id="salesforce",
    bundle="salesforce",
    kinds=(
        TriggerKind(
            kind="salesforce.record",
            component="SalesforceOnRecordTriggerComponent",
            display_name="Salesforce On Record Change",
            config_fields=("connection", "delivery_mode", "object_name", "fields"),
            required_scopes=("api", "refresh_token"),
            poll_mechanism="salesforce.record.poll",
        ),
    ),
    normalize_config=normalize_config,
    collect=collect,
    prepare=prepare,
    api_origins=OAUTH.allowed_origins,
    oauth=OAUTH,
)
