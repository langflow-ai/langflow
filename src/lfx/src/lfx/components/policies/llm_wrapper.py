from toolguard.llm.tg_litellm import LanguageModelBase
from langchain_core.messages import messages_from_dict
from typing import Dict, List
from langchain_core.language_models.chat_models import BaseChatModel

class LangchainModelWrapper(LanguageModelBase):

	def __init__(self, langchain_model:BaseChatModel):
		super().__init__(model_name = langchain_model.model_name) # type: ignore
		self.langchain_model = langchain_model

	async def generate(self, messages: List[Dict])->str:
		messages = [{
		    'type': 'human' if msg['role'] == 'user' else 'system', 
		    'data':{
                'content': msg['content']
            }
		} for msg in messages]
		lc_messages = messages_from_dict(messages)
		response = await self.langchain_model.agenerate(
			messages=[lc_messages],
		)
		return response.generations[0][0].message.content