from langchain_community.chat_message_histories.redis import RedisChatMessageHistory
from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import MessageTextInput, SecretStrInput, StrInput, IntInput
from langflow.field_typing import BaseChatMessageHistory
from urllib import parse

class RedisIndexChatMemory(LCChatMemoryComponent):
    display_name = "Redis Chat Memory"
    description = "Retrieves and store chat messages from Redis."
    name = "RedisChatMemory"
    icon = "Redis"

    inputs = [
        StrInput(name="host", display_name="hostname", required=True,
                 value="localhost", info="IP address or hostname."),
        IntInput(name="port", display_name="port", required=True,
                 value=6379, info="Redis Port Number."),
        StrInput(name="database", display_name="database", required=True,
                 value="0", info="Redis database."),
        MessageTextInput(name="username", display_name="Username", value="",
                         info="The Redis user name.", advanced=True),
        SecretStrInput(name="password", display_name="Password", value="",
                       info="The password for username.", advanced=True),
        StrInput(name="key_prefix", display_name="Key prefix",
                       info="Key prefix.", advanced=True),
        MessageTextInput(
            name="session_id", display_name="Session ID",
            info="Session ID for the message.", advanced=True
        ),
    ]

    def build_message_history(self) -> BaseChatMessageHistory:
        kwargs = {}
        if self.key_prefix:
            kwargs["key_prefix"] = self.key_prefix
        if self.password is not None and self.password != "":
            self.password = parse.quote_plus(self.password)

        url = f"redis://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        return RedisChatMessageHistory(session_id=self.session_id, url=url, **kwargs)