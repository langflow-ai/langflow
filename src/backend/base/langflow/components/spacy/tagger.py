from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, HandleInput, Output
from langflow.schema import Data
from typing import Any, Dict, List
import spacy
from spacy.language import Language
from spacy.tokens import Doc

class SpacyTagger(Component):
    display_name = "Spacy Tagger"
    description = "Component for part-of-speech tagging using spaCy models."
    icon = "tag"

    inputs = [
        DataInput(name="data_inputs", display_name="Data Inputs", info="Data containing the text to be tagged", is_list=True),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"]
        ),
        DropdownInput(
            name="attribute", 
            display_name="Attribute", 
            options=["POS", "TAG", "DEP"],
            value="TAG",
            info="The attribute to tag (POS: coarse-grained part-of-speech, TAG: fine-grained part-of-speech, DEP: syntactic dependency)"
        )
    ]

    outputs = [
        Output(name="tagged_data", display_name="Tagged Data", method="process")
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.tagger = None

    def process(self) -> Data:
        try:
            self.validate_inputs()
            
            results = []
            for input_data in self.data_inputs:
                if isinstance(input_data, Data):
                    text = input_data.text
                else:
                    text = str(input_data)

                if not text.strip():
                    continue

                doc = self.spacy_model(text)
                tagged_result = self.tag_doc(doc)
                results.append(tagged_result)

            # Wrap the results in a dictionary
            return Data(data={"results": results})
        except Exception as e:
            return Data(data={"error": str(e)})

    def tag_doc(self, doc: Doc) -> Dict[str, Any]:
        tokens = []
        text_tagged = []
        for token in doc:
            if self.attribute == "POS":
                tag = token.pos_
            elif self.attribute == "TAG":
                tag = token.tag_
            elif self.attribute == "DEP":
                tag = token.dep_
            else:
                tag = "Unknown"
            
            tokens.append({
                "text": token.text,
                "tag": tag,
                "start": token.idx,
                "end": token.idx + len(token.text)
            })
            text_tagged.append(f"{token.text}<{tag}>")
        
        return {
            "text": doc.text,
            "attribute": self.attribute,
            "tokens": tokens,
            "text_tagged": " ".join(text_tagged)
        }

    def validate_inputs(self):
        if not self.data_inputs:
            raise ValueError("Data input is required")
        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")
        if self.attribute not in ["POS", "TAG", "DEP"]:
            raise ValueError("Invalid attribute. Must be one of POS, TAG, or DEP.")

    def update_build_config(self, build_config: Dict[str, Any], field_value: Any, field_name: str | None = None) -> Dict[str, Any]:
        return build_config
