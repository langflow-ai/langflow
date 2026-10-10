"""Backward-compatible imports for source components with independently serialized code."""

from .calendar_trigger import MicrosoftOnCalendarTriggerComponent
from .file_trigger import MicrosoftOnFileTriggerComponent
from .mail_trigger import MicrosoftOnMailTriggerComponent

__all__ = [
    "MicrosoftOnCalendarTriggerComponent",
    "MicrosoftOnFileTriggerComponent",
    "MicrosoftOnMailTriggerComponent",
]
