"""Schema mapping between Langflow and Stepflow formats."""

from typing import Any


class SchemaMapper:
    """Maps schemas between Langflow and Stepflow formats."""

    def __init__(self):
        """Initialize schema mapper with type mappings."""
        self.langflow_to_json_schema = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "dropdown": "string",
            "slider": "number",
            "file": "string",
            "code": "string",
            "prompt": "string",
            "multiline": "string",
        }

        # component_output_heuristics: Maps Langflow component types to their expected
        # output data types. This is used as a fallback when component output metadata
        # is not available in the node definition. For example, ChatInput components
        # typically output Message objects, while VectorStore components output
        # DataFrame objects. These heuristics help generate proper output schemas
        # during conversion.
        self.component_output_heuristics = {
            "ChatInput": ["Message"],
            "ChatOutput": ["Message"],
            "LanguageModelComponent": ["Message"],
            "PromptComponent": ["Message"],
            "TextSplitter": ["Data"],
            "DocumentLoader": ["Data"],
            "VectorStore": ["DataFrame"],
            "Embeddings": ["DataFrame"],
        }

    def extract_output_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        """Extract output schema from a Langflow node.

        Args:
            node: Langflow node object

        Returns:
            JSON schema for the node's output
        """
        node_data = node.get("data", {})
        component_type = node_data.get("type", "")

        # Method 1: Check node outputs metadata
        outputs = node_data.get("outputs", [])
        if outputs:
            return self._convert_langflow_outputs_to_schema(outputs)

        # Method 2: Check base classes
        base_classes = node_data.get("base_classes", [])
        if base_classes:
            return self._convert_langflow_types_to_schema(base_classes)

        # Method 3: Use component type heuristics
        if component_type in self.component_output_heuristics:
            types = self.component_output_heuristics[component_type]
            return self._convert_langflow_types_to_schema(types)

        # Fallback: generic object schema
        return {"type": "object", "properties": {"result": {"type": "object"}}}

    def extract_input_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        """Extract input schema from a Langflow node template.

        Args:
            node: Langflow node object

        Returns:
            JSON schema for the node's inputs
        """
        node_data = node.get("data", {})
        template = node_data.get("node", {}).get("template", {})

        properties = {}
        required = []

        for field_name, field_config in template.items():
            if field_name.startswith("_") or not isinstance(field_config, dict):
                continue

            field_type = field_config.get("type", "str")
            json_type = self.langflow_to_json_schema.get(field_type, "string")
            field_info = field_config.get("info", "")

            property = {
                "type": json_type,
                "description": field_info,
            }

            # Add enum for dropdown fields
            if field_type == "dropdown" and "options" in field_config:
                property["enum"] = field_config["options"]

            # Add number constraints for sliders
            if field_type == "slider":
                if "range_spec" in field_config:
                    range_spec = field_config["range_spec"]
                    if "min" in range_spec:
                        property["minimum"] = range_spec["min"]
                    if "max" in range_spec:
                        property["maximum"] = range_spec["max"]

            if field_config.get("password", False) or field_config.get("_input_type", "") == "SecretStrInput":
                property["is_secret"] = True

            if field_config.get("required", False):
                required.append(field_name)

            properties[field_name] = property

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def _convert_langflow_outputs_to_schema(self, outputs: list[dict[str, Any]]) -> dict[str, Any]:
        """Convert Langflow outputs metadata to JSON schema."""
        if not outputs:
            return {"type": "object"}

        # For now, use the first output
        # TODO: Handle multiple outputs properly
        first_output = outputs[0]
        output_types = first_output.get("types", ["object"])

        return self._convert_langflow_types_to_schema(output_types)

    def _convert_langflow_types_to_schema(self, langflow_types: list[str]) -> dict[str, Any]:
        """Convert Langflow types to JSON schema.

        Args:
            langflow_types: List of Langflow type names

        Returns:
            JSON schema object
        """
        if "Message" in langflow_types:
            return {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "sender": {"type": "string"},
                    "sender_name": {"type": "string"},
                    "type": {"type": "string", "const": "Message"},
                },
            }
        elif "Data" in langflow_types:
            return {
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                    "text_key": {"type": "string"},
                    "type": {"type": "string", "const": "Data"},
                },
            }
        elif "DataFrame" in langflow_types:
            return {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}},
                    "type": {"type": "string", "const": "DataFrame"},
                },
            }
        else:
            # Generic object for unknown types
            return {"type": "object", "properties": {"result": {"type": "object"}}}
