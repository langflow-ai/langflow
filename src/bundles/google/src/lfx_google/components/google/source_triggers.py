"""Backward-compatible imports for source components with independently serialized code."""

from .calendar_trigger import GoogleOnCalendarTriggerComponent
from .drive_trigger import GoogleOnDriveTriggerComponent
from .gmail_trigger import GoogleOnGmailTriggerComponent

__all__ = [
    "GoogleOnCalendarTriggerComponent",
    "GoogleOnDriveTriggerComponent",
    "GoogleOnGmailTriggerComponent",
]
