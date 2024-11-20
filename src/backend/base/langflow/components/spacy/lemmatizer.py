from typing import Optional
from langflow.custom import Component
from langflow.io import DropdownInput, BoolInput, MessageTextInput, Output, HandleInput
from langflow.schema.message import Message
from spacy.language import Language

class SpacyLemmatizerComponent(Component):
    display_name = "Lemmatizer"
    description = "Apply lemmatization to text using SpaCy."
    icon = "scissors"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Text to Lemmatize",
            placeholder="Enter text to lemmatize",
            info="The input text to be lemmatized",
            required=True
        ),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"]
        ),
        DropdownInput(
            name="lemmatizer_mode",
            display_name="Mode",
            info="The lemmatizer mode to use",
            options=["rule", "lookup"],
            value="rule"
        ),
        BoolInput(
            name="keep_spacing",
            display_name="Keep Spaces",
            info="Whether to keep original spacing",
            value=True
        )
    ]

    outputs = [
        Output(display_name="Lemmatized Text", name="lemmatized_result", method="lemmatize_text")
    ]

    def _get_input_text(self) -> str:
        """Extract input text from component attributes"""
        input_text = self.input_value
        
        if isinstance(input_text, Message):
            return input_text.text
        elif isinstance(input_text, str):
            return input_text
        elif input_text is None:
            return ""
        else:
            return str(input_text)

    def lemmatize_text(self) -> Message:
        """Lemmatize the input text"""
        # Get input text
        text = self._get_input_text()
        if not text.strip():
            return Message(text="")

        try:
            # Check if spacy_model is provided and is a valid Language object
            if not isinstance(self.spacy_model, Language):
                raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")

            # Process text
            doc = self.spacy_model(text)
            
            # Get lemmatization settings
            keep_spacing = getattr(self, 'keep_spacing', True)
            
            # Generate lemmatized text
            if keep_spacing:
                result = "".join(
                    token.text_with_ws if token.text.isspace()
                    else token.lemma_ + token.whitespace_
                    for token in doc
                )
            else:
                result = " ".join(token.lemma_ for token in doc if not token.is_space)

            return Message(text=result)

        except Exception as e:
            self.status = f"Error during lemmatization: {str(e)}"
            return Message(text=str(e))
