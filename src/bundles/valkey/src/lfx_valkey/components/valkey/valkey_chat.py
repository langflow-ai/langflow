from urllib import parse

from lfx.base.memory.model import LCChatMemoryComponent
from lfx.field_typing.constants import Memory
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput, StrInput


class ValkeyIndexChatMemory(LCChatMemoryComponent):
    display_name = "Valkey Chat Memory"
    description = "Retrieves and stores chat messages from Valkey."
    name = "ValkeyChatMemory"
    icon = "Valkey"

    inputs = [
        StrInput(
            name="host", display_name="Hostname", required=True, value="localhost", info="IP address or hostname."
        ),
        IntInput(name="port", display_name="Port", required=True, value=6379, info="Valkey Port Number."),
        StrInput(name="database", display_name="Database", required=True, value="0", info="Valkey database."),
        MessageTextInput(
            name="username", display_name="Username", value="", info="The Valkey user name.", advanced=True
        ),
        SecretStrInput(
            name="password",
            display_name="Valkey Password",
            info="Password for the specified username.",
            advanced=True,
            load_from_db=False,
        ),
        StrInput(name="key_prefix", display_name="Key prefix", info="Key prefix.", advanced=True),
        MessageTextInput(
            name="session_id", display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
    ]

    def build_message_history(self) -> Memory:
        from langchain_community.chat_message_histories.redis import RedisChatMessageHistory

        kwargs = {}
        if self.key_prefix:
            kwargs["key_prefix"] = self.key_prefix

        # Build URL, only include auth if credentials are actually provided
        password = getattr(self, "password", None)
        username = getattr(self, "username", None)
        has_password = bool(password) and str(password).strip() not in ("", "None")
        has_username = bool(username) and str(username).strip() not in ("", "None")

        if has_password:
            encoded_pw = parse.quote_plus(str(password))
            encoded_username = parse.quote_plus(str(username)) if has_username else ""
            auth = f"{encoded_username}:{encoded_pw}@"
        else:
            auth = ""

        url = f"redis://{auth}{self.host}:{self.port}/{self.database}"
        return RedisChatMessageHistory(session_id=self.session_id, url=url, **kwargs)
