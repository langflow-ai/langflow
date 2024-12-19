from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, FloatInput, MessageTextInput, Output, HandleInput
from langflow.schema import Data
from typing import Any, Dict, Optional, List
import spacy
from spacy.language import Language
from spacy.tokens import Doc
import numpy as np

class SpacyTextCategorizer(Component):
    display_name = "Text Categorizer"
    description = "Component that uses spaCy for text classification, supporting single-label (textcat) and multi-label (textcat_multilabel) classification."
    icon = "highlighter"

    inputs = [
        DataInput(name="data_inputs", display_name="Data Inputs", info="Data containing the text to be classified", is_list=True),
        DropdownInput(
            name="mode", 
            display_name="Mode", 
            options=["textcat", "textcat_multilabel"],
            value="textcat",
            info="Classification mode",
            refresh_button=True
        ),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"]
        ),
        MessageTextInput(name="categories", display_name="Categories", info="List of categories for classification (comma-separated)"),
        FloatInput(
            name="threshold", 
            display_name="Threshold", 
            value=0.5,
            info="Threshold for considering a prediction 'positive' (for textcat_multilabel)"
        ),
        MessageTextInput(
            name="positive_label", 
            display_name="Positive Label", 
            info="Positive category for binary classification (for textcat)"
        )
    ]

    outputs = [
        Output(name="classification_result", display_name="Classification Result", method="process")
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.textcat = None

    def build(self):
        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")

        self.nlp = self.spacy_model
        
        if self.mode not in self.nlp.pipe_names:
            config = {"threshold": self.threshold} if self.mode == "textcat_multilabel" else {}
            self.nlp.add_pipe(self.mode, config=config)
        
        self.textcat = self.nlp.get_pipe(self.mode)
        
        if self.categories:
            categories = [cat.strip() for cat in self.categories.split(',')]
            for cat in categories:
                self.textcat.add_label(cat)
        
        if self.mode == "textcat" and self.positive_label:
            self.textcat.cfg["positive_label"] = self.positive_label.strip()

        # Initialize the model
        self.nlp.initialize()

    def process(self) -> Data:
        try:
            self.validate_inputs()
            self.build()
            
            results = []
            for input_data in self.data_inputs:
                if isinstance(input_data, Data):
                    text = input_data.text
                else:
                    text = str(input_data)

                if not text.strip():
                    continue

                doc = self.nlp(text)
                result = self.classify_text(doc)
                results.append(result)

            combined_result = {
                "classification_results": results,
                "num_processed_inputs": len(results),
                "mode": self.mode,
                "categories": self.categories,
                "threshold": self.threshold if self.mode == "textcat_multilabel" else None,
                "positive_label": self.positive_label if self.mode == "textcat" else None
            }

            return Data(data=combined_result)
        except Exception as e:
            return Data(data={"error": str(e)})

    def classify_text(self, doc: Doc) -> Dict[str, Any]:
        cats = doc.cats
        
        if self.mode == "textcat":
            predicted = max(cats, key=cats.get)
            confidence = cats[predicted]
            result = {
                "predicted_category": predicted,
                "scores": {k: round(float(v), 4) for k, v in cats.items()},
                "confidence": round(float(confidence), 4),
                "positive_label": self.positive_label
            }
        else:  # textcat_multilabel
            predicted_categories = [cat for cat, score in cats.items() if score >= self.threshold]
            result = {
                "predicted_categories": predicted_categories,
                "scores": {k: round(float(v), 4) for k, v in cats.items()},
                "num_predicted_labels": len(predicted_categories),
                "avg_confidence": round(float(np.mean([cats[cat] for cat in predicted_categories])) if predicted_categories else 0, 4),
                "threshold": self.threshold
            }
        
        return result

    def validate_inputs(self):
        if not self.data_inputs:
            raise ValueError("Data input is required")
        if self.mode not in ["textcat", "textcat_multilabel"]:
            raise ValueError("Invalid mode")
        if not self.categories:
            raise ValueError("At least one category must be defined")
        
        categories = [cat.strip() for cat in self.categories.split(',')]
        
        if self.mode == "textcat":
            if len(categories) != 2:
                raise ValueError("'textcat' mode requires exactly two categories")
            if not self.positive_label:
                raise ValueError("A positive label must be selected for 'textcat' mode")
            if self.positive_label.strip() not in categories:
                raise ValueError("The positive label must be in the list of categories")
        else:  # textcat_multilabel
            if len(categories) < 2:
                raise ValueError("'textcat_multilabel' mode requires at least two categories")
            if self.threshold is None or self.threshold < 0 or self.threshold > 1:
                raise ValueError("Threshold must be between 0 and 1 for 'textcat_multilabel' mode")

    def update_build_config(self, build_config: Dict[str, Any], field_value: Any, field_name: str | None = None) -> Dict[str, Any]:
        if field_name == "mode":
            if field_value == "textcat":
                build_config["threshold"]["show"] = False
                build_config["positive_label"]["show"] = True
            elif field_value == "textcat_multilabel":
                build_config["threshold"]["show"] = True
                build_config["positive_label"]["show"] = False
        return build_config
