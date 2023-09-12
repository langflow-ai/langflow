from langflow import CustomComponent


class ChatInput(CustomComponent):
    display_name = "Chat Input"

    def build(self, message: str) -> str:
        return message
