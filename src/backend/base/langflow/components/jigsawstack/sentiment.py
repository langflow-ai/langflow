from lfx.custom.custom_component.component import Component

from langflow.io import MessageTextInput, Output, SecretStrInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class JigsawStackSentimentComponent(Component):
    display_name = "Sentiment Analysis"
    description = "Analyze sentiment of text using JigsawStack AI"
    documentation = "https://jigsawstack.com/docs/api-reference/ai/sentiment"
    icon = "JigsawStack"
    name = "JigsawStackSentiment"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="Text to analyze for sentiment",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Sentiment Data", name="sentiment_data", method="analyze_sentiment"),
        Output(display_name="Sentiment Text", name="sentiment_text", method="get_sentiment_text"),
    ]

    def analyze_sentiment(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)
            response = client.sentiment({"text": self.text})

            api_error_msg = "JigsawStack API returned unsuccessful response"
            if not response.get("success", False):
                raise ValueError(api_error_msg)

            sentiment_data = response.get("sentiment", {})

            result_data = {
                "text_analyzed": self.text,
                "sentiment": sentiment_data.get("sentiment", "Unknown"),
                "emotion": sentiment_data.get("emotion", "Unknown"),
                "score": sentiment_data.get("score", 0.0),
                "sentences": response.get("sentences", []),
                "success": True,
            }

            self.status = (
                f"Sentiment: {sentiment_data.get('sentiment', 'Unknown')} | "
                f"Emotion: {sentiment_data.get('emotion', 'Unknown')} | "
                f"Score: {sentiment_data.get('score', 0.0):.3f}"
            )

            return Data(data=result_data)

        except JigsawStackError as e:
            error_data = {"error": str(e), "text_analyzed": self.text, "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)

    def get_sentiment_text(self) -> Message:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError:
            return Message(text="Error: JigsawStack package not found. Please install it with: pip install jigsawstack")

        try:
            client = JigsawStack(api_key=self.api_key)
            response = client.sentiment({"text": self.text})

            sentiment_data = response.get("sentiment", {})
            sentences = response.get("sentences", [])

            # Format the output
            formatted_output = f"""Sentiment Analysis Results:

Text: {self.text}

Overall Sentiment: {sentiment_data.get("sentiment", "Unknown")}
Emotion: {sentiment_data.get("emotion", "Unknown")}
Score: {sentiment_data.get("score", 0.0):.3f}

Sentence-by-sentence Analysis:
"""

            for i, sentence in enumerate(sentences, 1):
                formatted_output += (
                    f"{i}. {sentence.get('text', '')}\n"
                    f"   Sentiment: {sentence.get('sentiment', 'Unknown')} | "
                    f"Emotion: {sentence.get('emotion', 'Unknown')} | "
                    f"Score: {sentence.get('score', 0.0):.3f}\n"
                )

            return Message(text=formatted_output)

        except JigsawStackError as e:
            return Message(text=f"Error analyzing sentiment: {e!s}")
