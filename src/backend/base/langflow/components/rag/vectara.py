from langflow.custom import CustomComponent
from langflow.schema.message import Message


class VectaraRag(CustomComponent):
    display_name = "Vectara RAG"
    description = "Vectara's full end to end RAG"
    documentation = "https://docs.vectara.com/docs"
    icon = "Vectara"
    name = "VectaraRAG"

    field_order = ["vectara_customer_id", "vectara_corpus_id", "vectara_api_key", "search_query", "reranker"]

    def build_config(self) -> dict:
        SUMMARIZER_PROMPTS = [
            "vectara-summary-ext-24-05-sml",
            "vectara-summary-ext-24-05-med-omni",
            "vectara-summary-ext-24-05-large",
            "vectara-summary-ext-24-05-med",
            "vectara-summary-ext-v1.3.0",
        ]

        RERANKER_TYPES = ["mmr", "rerank_multilingual_v1", "none"]

        return {
            "vectara_customer_id": {"display_name": "Vectara Customer ID", "field_type": "str", "required": True},
            "vectara_corpus_id": {"display_name": "Vectara Corpus ID", "field_type": "str", "required": True},
            "vectara_api_key": {"display_name": "Vectara API Key", "field_type": "str", "required": True},
            "search_query": {
                "display_name": "Search Query",
                "field_type": "str",
                "info": "The query to receive an answer on.",
                "required": True,
            },
            "lexical_interpolation": {
                "display_name": "Hybrid Search Factor",
                "field_type": "float",
                "value": 0.005,
                "info": "How much to weigh lexical scores compared to the embedding score. 0 means lexical search is not used at all, and 1 means only lexical search is used.",
                "advanced": True,
            },
            "filter": {
                "display_name": "Metadata Filters",
                "field_type": "str",
                "value": "",
                "info": "The filter string to narrow the search to according to metadata attributes.",
                "advanced": True,
            },
            "reranker": {
                "display_name": "Reranker Type",
                "options": RERANKER_TYPES,
                "value": RERANKER_TYPES[0],
                "info": "How to rerank the retrieved search results.",
            },
            "reranker_k": {
                "display_name": "Number of Results to Rerank",
                "field_type": "int",
                "value": 50,
                "advanced": True,
            },
            "diversity_bias": {
                "display_name": "Diversity Bias",
                "field_type": "float",
                "value": 0.2,
                "info": "Ranges from 0 to 1, with higher values indicating greater diversity (only applies to MMR reranker).",
                "advanced": True,
            },
            "max_results": {
                "display_name": "Max Results to Summarize",
                "field_type": "int",
                "value": 7,
                "info": "The maximum number of search results to be available to the prompt.",
                "advanced": True,
            },
            "response_lang": {
                "display_name": "Response Language",
                "field_type": "str",
                "value": "eng",
                "info": "Use the ISO 639-1 or 639-3 language code or auto to automatically detect the language.",
                "advanced": True,
            },
            "prompt": {
                "display_name": "Prompt Name",
                "options": SUMMARIZER_PROMPTS,
                "value": SUMMARIZER_PROMPTS[0],
                "info": "Only vectara-summary-ext-24-05-sml is for Growth customers; all other prompts are for Scale customers only.",
                "advanced": True,
            },
        }

    def build(
        self,
        vectara_customer_id: str,
        vectara_corpus_id: str,
        vectara_api_key: str,
        search_query: str,
        lexical_interpolation: float = 0.005,
        filter: str = "",
        reranker: str = "mmr",
        reranker_k: int = 50,
        diversity_bias: float = 0.2,
        max_results: int = 7,
        response_lang: str = "eng",
        prompt: str = "vectara-summary-ext-24-05-sml",
    ) -> Message:
        text_output = ""

        try:
            from langchain_community.vectorstores import Vectara
            from langchain_community.vectorstores.vectara import RerankConfig, VectaraQueryConfig, SummaryConfig
        except ImportError:
            raise ImportError("Could not import Vectara. Please install it with `pip install langchain-community`.")

        vectara = Vectara(vectara_customer_id, vectara_corpus_id, vectara_api_key)
        rerank_config = RerankConfig(reranker, reranker_k, diversity_bias)
        summary_config = SummaryConfig(
            is_enabled=True, max_results=max_results, response_lang=response_lang, prompt_name=prompt
        )
        config = VectaraQueryConfig(
            lambda_val=lexical_interpolation, filter=filter, summary_config=summary_config, rerank_config=rerank_config
        )
        rag = vectara.as_rag(config)
        response = rag.invoke(search_query)

        text_output = response["answer"]

        return Message(text=text_output)
