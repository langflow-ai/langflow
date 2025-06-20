from langflow.custom.custom_component.component import Component
from langflow.io import Output, SecretStrInput, StrInput, IntInput
from langflow.schema.data import Data


class JigsawStackNSFWComponent(Component):
    display_name = "NSFW"
    description = "Quickly detect nudity, violence, hentai, porn and more NSFW content in images."
    documentation = "https://jigsawstack.com/docs/api-reference/validate/nsfw"
    icon = "JigsawStack"
    name = "JigsawStackNSFW"
    
    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        StrInput(
            name="url",
            display_name="URL",
            info="The image URL to validate.",
            required=True,
        )
    ]

    outputs = [
        Output(display_name="NSFW Results", name="nsfw_results", method="nsfw"),
    ]

    def nsfw(self) -> Data:
        try:
            from jigsawstack import JigsawStack
        except ImportError as e:
            raise ImportError(
                "JigsawStack package not found"
            ) from e

        try:
            client = JigsawStack(api_key=self.api_key)
            
            #build request object
            params = {}
            if self.url:
                params["url"] = self.url
        
            # Call web scraping
            response = client.validate.nsfw(params)
            
            if not response.get("success", False):
                raise ValueError("JigsawStack API returned unsuccessful response")
            
            return Data(data=response)
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "success": False
            }
            self.status = f"Error: {str(e)}"
            return Data(data=error_data)


   