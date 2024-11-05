import warnings

from langchain_core._api.deprecation import LangChainDeprecationWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", LangChainDeprecationWarning)
    from .aiml import AIMLEmbeddingsImpl


__all__ = ["AIMLEmbeddingsImpl"]
