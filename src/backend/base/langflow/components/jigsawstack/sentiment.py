from typing import Any

from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class JigsawStackSentimentComponent(Component):
    display_name = "Sentiment Analysis"
    description = "Analyze sentiment and emotion in text using JigsawStack AI"
    documentation = "https://docs.jigsawstack.com/api-reference/ai/sentiment"
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
            info="The text to analyze for sentiment and emotion",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Sentiment Result", name="sentiment_result", method="analyze_sentiment"),
        Output(display_name="Formatted Text", name="formatted_text", method="get_formatted_text"),
    ]

    def analyze_sentiment(self) -> Data:
        try:
            from jigsawstack import JigsawStack
        except ImportError as e:
            raise ImportError(
                "JigsawStack package not found. Please install it with: pip install jigsawstack"
            ) from e

        try:
            # Initialize JigsawStack client
            client = JigsawStack(api_key=self.api_key)
            
            # Call sentiment analysis
            response = client.sentiment({"text": self.text})
            
            if not response.get("success", False):
                raise ValueError("JigsawStack API returned unsuccessful response")
            
            sentiment_data = response.get("sentiment", {})
            
            # Create comprehensive data object
            result_data = {
                "overall_sentiment": sentiment_data.get("sentiment", ""),
                "overall_emotion": sentiment_data.get("emotion", ""),
                "overall_score": sentiment_data.get("score", 0.0),
                "sentences": sentiment_data.get("sentences", []),
                "text_analyzed": self.text,
                "success": True
            }
            
            self.status = f"Sentiment: {sentiment_data.get('sentiment', 'Unknown')} | Emotion: {sentiment_data.get('emotion', 'Unknown')} | Score: {sentiment_data.get('score', 0.0):.3f}"
            
            return Data(data=result_data)
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "text_analyzed": self.text,
                "success": False
            }
            self.status = f"Error: {str(e)}"
            return Data(data=error_data)

    def get_formatted_text(self) -> Message:
        try:
            from jigsawstack import JigsawStack
        except ImportError as e:
            return Message(text=f"Error: JigsawStack package not found. Please install it with: pip install jigsawstack")

        try:
            # Initialize JigsawStack client
            client = JigsawStack(api_key=self.api_key)
            
            # Call sentiment analysis
            response = client.sentiment({"text": self.text})
            
            if not response.get("success", False):
                return Message(text="Error: JigsawStack API returned unsuccessful response")
            
            sentiment_data = response.get("sentiment", {})
            
            # Create formatted text output
            formatted_output = f"""📊 **Sentiment Analysis Results**

**Overall Analysis:**
• Sentiment: {sentiment_data.get('sentiment', 'Unknown')}
• Emotion: {sentiment_data.get('emotion', 'Unknown')}
• Confidence Score: {sentiment_data.get('score', 0.0):.3f}

**Original Text:**
"{self.text}"

**Sentence-by-Sentence Breakdown:**"""

            sentences = sentiment_data.get("sentences", [])
            for i, sentence in enumerate(sentences, 1):
                formatted_output += f"""

{i}. "{sentence.get('text', '')}"
   → Sentiment: {sentence.get('sentiment', 'Unknown')} | Emotion: {sentence.get('emotion', 'Unknown')} | Score: {sentence.get('score', 0.0):.3f}"""

            return Message(text=formatted_output)
            
        except Exception as e:
            return Message(text=f"Error analyzing sentiment: {str(e)}")