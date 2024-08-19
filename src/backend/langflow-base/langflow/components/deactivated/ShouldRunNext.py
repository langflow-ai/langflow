from langchain_core.messages import BaseMessage
from langchain_core.prompts import PromptTemplate

from langflow.custom import CustomComponent
from langflow.field_typing import LanguageModel, Text


class ShouldRunNextComponent(CustomComponent):
    display_name = "Should Run Next"
    description = "Determines if a vertex is runnable."
    name = "ShouldRunNext"

    def build(self, llm: LanguageModel, question: str, context: str, retries: int = 3) -> Text:
        template = "Given the following question and the context below, answer with a yes or no.\n\n{error_message}\n\nQuestion: {question}\n\nContext: {context}\n\nAnswer:"

        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm
        error_message = ""
        for i in range(retries):
            result = chain.invoke(
                dict(question=question, context=context, error_message=error_message),
                config={"callbacks": self.get_langchain_callbacks()},
            )
            if isinstance(result, BaseMessage):
                content = result.content
            elif isinstance(result, str):
                content = result
            if isinstance(content, str) and content.lower().strip() in ["yes", "no"]:
                break
        condition = str(content).lower().strip() == "yes"
        self.status = f"Should Run Next: {condition}"
        if condition is False:
            self.stop()
        return context
