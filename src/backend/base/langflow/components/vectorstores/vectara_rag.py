from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output
from langflow.schema.message import Message


class VectaraRagComponent(Component):
    display_name = "Vectara RAG"
    description = "Vectara's full end to end RAG"
    documentation = "https://docs.vectara.com/docs"
    icon = "Vectara"
    name = "VectaraRAG"
    SUMMARIZER_PROMPTS = [
        "vectara-summary-ext-24-05-sml",
        "vectara-summary-ext-24-05-med-omni",
        "vectara-summary-ext-24-05-large",
        "vectara-summary-ext-24-05-med",
        "vectara-summary-ext-v1.3.0",
    ]

    RERANKER_TYPES = ["mmr", "rerank_multilingual_v1", "none"]

    field_order = ["vectara_customer_id", "vectara_corpus_id", "vectara_api_key", "search_query", "reranker"]
    #  return {
    #         "vectara_customer_id": {"display_name": "Vectara Customer ID", "field_type": "str", "required": True},
    #         "vectara_corpus_id": {"display_name": "Vectara Corpus ID", "field_type": "str", "required": True},
    #         "vectara_api_key": {"display_name": "Vectara API Key", "field_type": "str", "required": True},
    #         "search_query": {"display_name": "Search Query", "field_type": "str", "info": "The query to receive an answer on.", "required": True},
    #         "lexical_interpolation": {"display_name": "Hybrid Search Factor", "field_type": "float", "value": 0.005, "info": "How much to weigh lexical scores compared to the embedding score. 0 means lexical search is not used at all, and 1 means only lexical search is used.", "advanced": True},
    #         "filter": {"display_name": "Metadata Filters", "field_type": "str", "value": '', "info": "The filter string to narrow the search to according to metadata attributes.", "advanced": True},
    #         "reranker": {"display_name": "Reranker Type", "options": RERANKER_TYPES, "value": RERANKER_TYPES[0], "info": "How to rerank the retrieved search results."},
    #         "reranker_k": {"display_name": "Number of Results to Rerank", "field_type": "int", "value": 50, "advanced": True},
    #         "diversity_bias": {"display_name": "Diversity Bias", "field_type": "float", "value": 0.2, "info": "Ranges from 0 to 1, with higher values indicating greater diversity (only applies to MMR reranker).", "advanced": True},
    #         "max_results": {"display_name": "Max Results to Summarize", "field_type": "int", "value": 7, "info": "The maximum number of search results to be available to the prompt.", "advanced": True},
    #         "response_lang": {"display_name": "Response Language", "field_type": "str", "value": "eng", "info": "Use the ISO 639-1 or 639-3 language code or auto to automatically detect the language.", "advanced": True},
    #         "prompt": {"display_name": "Prompt Name", "options": SUMMARIZER_PROMPTS, "value": SUMMARIZER_PROMPTS[0], "info": "Only vectara-summary-ext-24-05-sml is for Growth customers; all other prompts are for Scale customers only.", "advanced": True}
    #     }

    inputs = [
        MessageTextInput(name="search_query", display_name="Search Query", info="The query to receive an answer on."),
        FloatInput(
            name="lexical_interpolation",
            display_name="Hybrid Search Factor",
            range_spec=RangeSpec(min=0.005, max=0.1, step=0.005),
            value=0.005,
            info="How much to weigh lexical scores compared to the embedding score. 0 means lexical search is not used at all, and 1 means only lexical search is used.",
        ),
        MessageTextInput(
            name="filter",
            display_name="Metadata Filters",
            value="",
            info="The filter string to narrow the search to according to metadata attributes.",
        ),
        DropdownInput(
            name="reranker",
            display_name="Reranker Type",
            options=RERANKER_TYPES,
            value=RERANKER_TYPES[0],
            info="How to rerank the retrieved search results.",
        ),
        IntInput(
            name="reranker_k",
            display_name="Number of Results to Rerank",
            value=50,
            range_spec=RangeSpec(min=1, max=100, step=1),
        ),
        FloatInput(
            name="diversity_bias",
            display_name="Diversity Bias",
            value=0.2,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            info="Ranges from 0 to 1, with higher values indicating greater diversity (only applies to MMR reranker).",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results to Summarize",
            value=7,
            range_spec=RangeSpec(min=1, max=100, step=1),
        ),
        DropdownInput(
            name="response_lang",
            display_name="Response Language",
            options=["auto", "eng", "deu", "fra", "ita", "nld", "por", "rus", "spa", "zho"],
            value="eng",
            info="Use the ISO 639-1 or 639-3 language code or auto to automatically detect the language.",
        ),
        DropdownInput(
            name="prompt",
            display_name="Prompt Name",
            options=SUMMARIZER_PROMPTS,
            value=SUMMARIZER_PROMPTS[0],
            info="Only vectara-summary-ext-24-05-sml is for Growth customers; all other prompts are for Scale customers only.",
        ),
    ]

    outputs = [
        Output(name="answer", display_name="Answer", method="generate_response"),
    ]

    def generate_response(
        self,
    ) -> Message:
        text_output = ""

        try:
            from langchain_community.vectorstores import Vectara
            from langchain_community.vectorstores.vectara import RerankConfig, SummaryConfig, VectaraQueryConfig
        except ImportError:
            raise ImportError("Could not import Vectara. Please install it with `pip install langchain-community`.")

        vectara = Vectara(self.vectara_customer_id, self.vectara_corpus_id, self.vectara_api_key)
        rerank_config = RerankConfig(self.reranker, self.reranker_k, self.diversity_bias)
        summary_config = SummaryConfig(
            is_enabled=True, max_results=self.max_results, response_lang=self.response_lang, prompt_name=self.prompt
        )
        config = VectaraQueryConfig(
            lambda_val=self.lexical_interpolation,
            filter=self.filter,
            summary_config=summary_config,
            rerank_config=rerank_config,
        )
        rag = vectara.as_rag(config)
        response = rag.invoke(self.search_query)

        text_output = response["answer"]

        return Message(text=text_output)
