from langflow.custom import Component


class TextComponent(Component):
    display_name = "Text Component"
    description = "Used to pass text to the next component."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Value",
                "input_types": ["Text", "Data"],
                "info": "Text or Data to be passed.",
            },
            "data_template": {
                "display_name": "Data Template",
                "multiline": True,
                "info": "Template to convert Data to Text. "
                "If left empty, it will be dynamically set to the Data's text key.",
                "advanced": True,
            },
        }
