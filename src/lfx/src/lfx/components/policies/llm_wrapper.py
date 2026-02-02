from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import messages_from_dict
from toolguard.buildtime.llm.tg_litellm import LanguageModelBase


class LangchainModelWrapper(LanguageModelBase):
    def __init__(self, langchain_model: BaseChatModel):
        self.langchain_model = langchain_model
        self.langchain_model.max_tokens = 10000

    async def generate(self, messages: list[dict]) -> str:
        messages = [
            {"type": "human" if msg["role"] == "user" else "system", "data": {"content": msg["content"]}}
            for msg in messages
        ]
        lc_messages = messages_from_dict(messages)
        response = await self.langchain_model.agenerate(
            messages=[lc_messages],
        )

        choice0 = response.generations[0][0]
        chunk = choice0.message.content
        if choice0.generation_info.get("finish_reason") == "length":  # max tokens reached
            next_messages = [
                *messages,
                choice0.message,
                {
                    "role": "user",
                    "content": (
                        "Continue the previous answer starting exactly from the last incomplete sentence.",
                        "Do not repeat anything.  Do not add any prefix.",
                    ),
                },
            ]
            return chunk + await self.generate(next_messages)
        return chunk
