from langchain_core.messages import BaseMessage
from langchain_core.prompts import PromptTemplate

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class ShouldRunNextComponent(CustomComponent):
    display_name = "Should Run Next"
    description = "Determines if a vertex is runnable."

    def build(self, llm: BaseLanguageModel, question: str, context: str, retries: int = 3):
        template = "Given the following question and the context below, answer with a yes or no.\n\n{error_message}\n\nQuestion: {question}\n\nContext: {context}\n\nAnswer:"

        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm
        error_message = ""
        for i in range(retries):
            result = chain.invoke(question=question, context=context, error_message=error_message)
            if isinstance(result, BaseMessage):
                content = result.content
            elif isinstance(result, str):
                content = result
            if content.lower().strip() in ["yes", "no"]:
                break
        condition = content.lower().strip() == "yes"
        result_dict = {"result": context, "condition": condition}
        self.status = result_dict
        return result_dict
