"""Discoverable Salesforce components with stable class identities."""

from .create_record import SalesforceCreateRecordComponent
from .read_record import SalesforceReadRecordComponent
from .record_trigger import SalesforceOnRecordTriggerComponent
from .update_record import SalesforceUpdateRecordComponent

__all__ = [
    "SalesforceCreateRecordComponent",
    "SalesforceOnRecordTriggerComponent",
    "SalesforceReadRecordComponent",
    "SalesforceUpdateRecordComponent",
]
