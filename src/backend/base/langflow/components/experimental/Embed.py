from langflow.custom import CustomComponent
from langflow.schema import Record
from langflow.field_typing import Embeddings


class EmbedComponent(CustomComponent):
    display_name = "Embed Texts"

    def build_config(self):
        return {"texts": {"display_name": "Texts"}, "embbedings": {"display_name": "Embeddings"}}

    def build(self, texts: list[str], embbedings: Embeddings) -> Embeddings:
        vectors = Record(vector=embbedings.embed_documents(texts))
        self.status = vectors
        return vectors
