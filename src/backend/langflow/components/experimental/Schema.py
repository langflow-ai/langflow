from langflow.custom import CustomComponent


class SchemaComponent(CustomComponent):
    display_name = "Schema"
    description = "Construct a Schema from a list of fields."

    def build_config(self):
        return {
            "fields": {
                "display_name": "Fields",
                "info": "The fields to include in the schema.",
            },
            "name": {
                "display_name": "Name",
                "info": "The name of the schema.",
            },
        }

    def build(self, name: str, fields: list[dict]):
        # The idea for this component is to use create_model from pydantic to create a schema
        # from a list of fields. This will be useful for creating schemas for the flow tool.
        pass

        # field is a simple list of dictionaries with the field name and
