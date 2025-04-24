from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings
from langflow.schema import JSON


class EmbedComponent(CustomComponent):
    display_name = "Embed Texts"
    name = "Embed"

    def build_config(self):
        return {"texts": {"display_name": "Texts"}, "embbedings": {"display_name": "Embeddings"}}

    def build(self, texts: list[str], embbedings: Embeddings) -> JSON:
        vectors = JSON(vector=embbedings.embed_documents(texts))
        self.status = vectors
        return vectors
