from langchain import llms
from langchain.llms.openai import OpenAIChat


llm_type_to_cls_dict = llms.type_to_cls_dict
llm_type_to_cls_dict["openai-chat"] = OpenAIChat
