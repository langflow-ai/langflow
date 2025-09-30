from fastapi.encoders import jsonable_encoder

from lfx.base.io.text import TextComponent
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class APIResponseComponent(TextComponent):
    display_name = "API Response"
    description = "Provides clean, stateless API responses with minimal JSON structure."
    icon = "code-xml"
    name = "APIResponse"
    beta = True

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Inputs",
            info="Data to be passed as output.",
            input_types=["Data", "DataFrame", "Message"],
            required=True,
        ),
    ]
    outputs = [
        Output(display_name="Response", name="output", method="output_response"),
    ]

    def _convert_input_to_output(self):
        """Convert input to appropriate output format based on type."""
        if isinstance(self.input_value, str):
            return {"text": self.input_value, "output_type": "text"}
        if isinstance(self.input_value, Message):
            return {"text": self.input_value.text, "output_type": "message"}
        if isinstance(self.input_value, Data):
            # Convert Data to JSON dict
            serializable_data = jsonable_encoder(self.input_value.data)
            return {"data": serializable_data, "output_type": "data"}
        if isinstance(self.input_value, DataFrame):
            # Convert DataFrame to list of records
            return {"records": self.input_value.to_dict("records"), "output_type": "dataframe"}
        # Fallback to string conversion
        return {"value": str(self.input_value), "output_type": "unknown"}

    def output_response(self) -> Message:
        # Create a minimal response structure
        import json
        import time
        from datetime import datetime, timezone

        start_time = time.time()

        # Convert input to appropriate output format
        output_data = self._convert_input_to_output()

        # Create the minimal output structure
        minimal_output = {
            "output": output_data,
            "metadata": {
                "flow_id": str(self.graph.flow_id) if hasattr(self, "graph") and self.graph.flow_id else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": int((time.time() - start_time) * 1000),
                "status": "complete",
                "error": False,
            },
        }

        # Return as JSON string in the Message to maintain structure
        message = Message(text=json.dumps(minimal_output))
        self.status = str(self.input_value)
        return message
