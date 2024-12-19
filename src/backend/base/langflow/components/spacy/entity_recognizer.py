from typing import List, Dict, Optional
from collections import defaultdict
from langflow.custom import Component
from langflow.io import HandleInput, DataInput, Output
from langflow.schema import Data
from spacy.language import Language
from spacy.tokens import Doc

class EntityRecognizerComponent(Component):
    display_name = "Entity Recognizer"
    description = "Named Entity Recognition using SpaCy models"
    icon = "tag"
    
    inputs = [
        DataInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="The data to be processed for entity recognition.",
            input_types=["Data"],
            is_list=True,
        ),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"]
        )
    ]
    
    outputs = [
        Output(display_name="Processed Text", name="processed_text", method="process_text"),
    ]

    def get_sentence_for_entity(self, doc: Doc, entity) -> str:
        """Get the sentence containing the entity."""
        for sent in doc.sents:
            if entity.start >= sent.start and entity.end <= sent.end:
                return sent.text
        return ""  # Fallback if sentence is not found

    def process_text(self) -> List[Data]:
        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")

        results = []
        for input_data in self.data_inputs:
            text = input_data.text if isinstance(input_data, Data) else str(input_data)
            doc = self.spacy_model(text)
            
            # Organize entities by type
            entities_by_type = defaultdict(list)
            for ent in doc.ents:
                sentence = self.get_sentence_for_entity(doc, ent)
                entities_by_type[ent.label_].append({
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "sentence": sentence
                })
            
            # Create a summary of entity counts
            entity_summary = {label: len(entities) for label, entities in entities_by_type.items()}
            
            # Create the final output structure
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

    def get_entity_examples(self, entity_type: str, max_examples: int = 5) -> List[Dict[str, str]]:
        """Get example entities with their sentences for a specific type."""
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