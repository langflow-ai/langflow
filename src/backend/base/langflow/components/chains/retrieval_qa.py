from langchain.chains import RetrievalQA

from langflow.base.chains.model import LCChainComponent
from langflow.field_typing import Message
from langflow.inputs import BoolInput, DropdownInput, HandleInput, MultilineInput


class RetrievalQAComponent(LCChainComponent):
    display_name = "Retrieval QA"
    description = "Chain for question-answering querying sources from a retriever."
    name = "RetrievalQA"

    inputs = [
        MultilineInput(
            name="input_value", display_name="Input", info="The input value to pass to the chain.", required=True
        ),
        DropdownInput(
            name="chain_type",
            display_name="Chain Type",
            info="Chain type to use.",
            options=["Stuff", "Map Reduce", "Refine", "Map Rerank"],
            value="Stuff",
            advanced=True,
        ),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        HandleInput(name="retriever", display_name="Retriever", input_types=["Retriever"], required=True),
        HandleInput(
            name="memory",
            display_name="Memory",
            input_types=["BaseChatMemory"],
        ),
        BoolInput(
            name="return_source_documents",
            display_name="Return Source Documents",
            value=False,
        ),
    ]

    def invoke_chain(self) -> Message:
        chain_type = self.chain_type.lower().replace(" ", "_")
        if self.memory:
            self.memory.input_key = "query"
            self.memory.output_key = "result"

        runnable = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type=chain_type,
            retriever=self.retriever,
            memory=self.memory,
            # always include to help debugging
            #
            return_source_documents=True,
        )

        result = runnable.invoke({"query": self.input_value}, config={"callbacks": self.get_langchain_callbacks()})

        source_docs = self.to_data(result.get("source_documents", keys=[]))
        result_str = str(result.get("result", ""))
        if self.return_source_documents and len(source_docs):
            references_str = self.create_references_from_data(source_docs)
            result_str = f"{result_str}\n{references_str}"
        # put the entire result to debug history, query and content
        self.status = {**result, "source_documents": source_docs, "output": result_str}
        return result_str
