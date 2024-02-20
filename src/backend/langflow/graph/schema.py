from enum import Enum


class InterfaceComponentTypes(Enum):
    # ChatInput and ChatOutput are the only ones that are
    # power components
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
