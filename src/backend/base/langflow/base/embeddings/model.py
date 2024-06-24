from langflow.custom import Component
from langflow.field_typing import Embeddings
from langflow.io import Output


class LCEmbeddingsModel(Component):
    trace_type = "embedding"

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def _validate_outputs(self):
        required_output_methods = ["build_embeddings"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def build_embeddings(self) -> Embeddings:
        raise NotImplementedError("You must implement the build_embeddings method in your class.")
