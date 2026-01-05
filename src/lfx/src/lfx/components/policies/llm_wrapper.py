from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import messages_from_dict
from toolguard.llm.tg_litellm import LanguageModelBase


def _model_name(lc_model: BaseChatModel) -> str:
    if hasattr(lc_model, "model_name"):  # eg. OpenAI
        return lc_model.model_name  # type: ignore reportAttributeAccessIssue
    if hasattr(lc_model, "model"):  # eg. Anthorpic
        return lc_model.model  # type: ignore reportAttributeAccessIssue
    return ""


class LangchainModelWrapper(LanguageModelBase):
    def __init__(self, langchain_model: BaseChatModel):
        super().__init__(model_name=_model_name(langchain_model))
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
        return response.generations[0][0].message.content
