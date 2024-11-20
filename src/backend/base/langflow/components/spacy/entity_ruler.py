from typing import List, Dict
from collections import defaultdict
from langflow.custom import Component
from langflow.io import DataInput, Output, HandleInput, BoolInput, TableInput
from langflow.schema import Data
from spacy.language import Language
from spacy.tokens import Doc

class SpacyEntityRuler(Component):
    display_name = "Spacy Entity Ruler"
    description = "Add rule-based named entity recognition to a spaCy pipeline."
    icon = "ruler"

    inputs = [
        DataInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="Texts to process for entity recognition",
            input_types=["Data"],
            is_list=True,
        ),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"],
            required=True
        ),
        TableInput(
            name="patterns",
            display_name="Entity Patterns",
            info="Define the patterns for entity recognition.",
            table_schema=[
                {
                    "name": "label",
                    "display_name": "Entity Label",
                    "type": "str",
                    "description": "The label for the entity (e.g., ORG, PERSON, PRODUCT)"
                },
                {
                    "name": "pattern",
                    "display_name": "Pattern",
                    "type": "str",
                    "description": "The text pattern to match (for phrase patterns)"
                },
                {
                    "name": "id",
                    "display_name": "Pattern ID",
                    "type": "str",
                    "description": "Optional unique identifier for the pattern",
                    "default": ""
                }
            ],
        ),
        BoolInput(
            name="overwrite_ents",
            display_name="Overwrite Entities",
            info="Whether to overwrite existing entities",
            value=False
        ),
    ]

    outputs = [
        Output(name="processed_data", display_name="Processed Data", method="process")
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.entity_ruler = None

    def _convert_patterns(self) -> List[Dict]:
        if not hasattr(self, 'patterns') or not self.patterns:
            return []

        converted_patterns = []
        for row in self.patterns:
            pattern = {
                "label": row["label"],
                "pattern": row["pattern"]
            }
            if row["id"]:
                pattern["id"] = row["id"]
            converted_patterns.append(pattern)
        return converted_patterns

    def get_sentence_for_entity(self, doc: Doc, entity) -> str:
        for sent in doc.sents:
            if entity.start >= sent.start and entity.end <= sent.end:
                return sent.text
        return ""

    def process(self) -> List[Data]:
        try:
            self.validate_inputs()
            
            self.entity_ruler = self.spacy_model.add_pipe("entity_ruler", config={"overwrite_ents": self.overwrite_ents})
            
            patterns = self._convert_patterns()
            self.entity_ruler.add_patterns(patterns)

            results = []
            for input_data in self.data_inputs:
                text = input_data.text if isinstance(input_data, Data) else str(input_data)

                if not text.strip():
                    continue

                doc = self.spacy_model(text)
                
                entities_by_type = defaultdict(list)
                for ent in doc.ents:
                    sentence = self.get_sentence_for_entity(doc, ent)
                    entities_by_type[ent.label_].append({
                        "text": ent.text,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "sentence": sentence
                    })
                
                entity_summary = {label: len(entities) for label, entities in entities_by_type.items()}
                
                processed_data = Data(
                    text=text,
                    data={
                        "entities_by_type": dict(entities_by_type),
                        "entity_summary": entity_summary,
                        "total_entities": len(doc.ents)
                    }
                )
                results.append(processed_data)

            self.status = results
            return results
        except Exception as e:
            return [Data(data={"error": str(e)})]

    def validate_inputs(self):
        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")
        if not self.patterns:
            raise ValueError("Patterns are required for the Entity Ruler.")
        if not self.data_inputs:
            raise ValueError("Data input is required")

    def get_entity_examples(self, entity_type: str, max_examples: int = 5) -> List[Dict[str, str]]:
        examples = []
        for result in self.status:
            entities = result.data["entities_by_type"].get(entity_type, [])
            for entity in entities[:max_examples]:
                examples.append({
                    "text": entity["text"],
                    "sentence": entity["sentence"]
                })
            if len(examples) >= max_examples:
                break
        return examples[:max_examples]
