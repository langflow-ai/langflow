from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class JigsawStackTextTranslateComponent(Component):
    display_name = "Text Translate"
    description = "Translate text from one language to another with support for multiple text formats."
    documentation = "https://jigsawstack.com/docs/api-reference/ai/translate"
    icon = "JigsawStack"
    name = "JigsawStackTextTranslate"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        StrInput(
            name="target_language",
            display_name="Target Language",
            info="The language code of the target language to translate to. \
                Language code is identified by a unique ISO 639-1 two-letter code",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="The text to translate. This can be a single string or a list of strings. \
                If a list is provided, each string will be translated separately.",
            required=True,
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Translation Results", name="transaltion_results", method="translation"),
    ]

    def translation(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.6"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)

            # build request object
            params = {}
            if self.target_language:
                params["target_language"] = self.target_language

            if self.text:
                if isinstance(self.text, list):
                    params["text"] = self.text
                else:
                    params["text"] = [self.text]

            # Call web scraping
            response = client.translate.text(params)

            if not response.get("success", False):
                failed_response_error = "JigsawStack API returned unsuccessful response"
                raise ValueError(failed_response_error)

            return Data(data=response)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
