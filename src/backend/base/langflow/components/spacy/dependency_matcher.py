from typing import List, Dict, Optional
from langflow.custom import Component
from langflow.io import DataInput, Output, HandleInput, BoolInput, MessageTextInput, TableInput
from langflow.schema import Data
from spacy.language import Language
from spacy.tokens import Doc
from spacy.matcher import DependencyMatcher
import json

class SpacyPatternMatcher(Component):
    """Component for identifying syntactic patterns using spaCy's dependency matcher"""
    display_name = "Dependency Matcher"
    description = "Identifies syntactic patterns in texts using spaCy's dependency matcher"
    icon = "search"

    inputs = [
        DataInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="Texts to analyze",
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
            name="pattern_schema",
            display_name="Pattern Schema",
            info="Define the dependency patterns to search for in the text.",
            table_schema=[
                {
                    "name": "pattern_name",
                    "display_name": "Pattern Name",
                    "type": "str",
                    "description": "Name of the pattern (e.g., ACTIVE_VOICE, PASSIVE_VOICE)"
                },
                {
                    "name": "right_id",
                    "display_name": "Right ID",
                    "type": "str",
                    "description": "Unique identifier for the token (e.g., verb, subject)"
                },
                {
                    "name": "pos",
                    "display_name": "POS",
                    "type": "str",
                    "description": "Part of speech tag (e.g., VERB, NOUN)",
                    "default": ""
                },
                {
                    "name": "dep",
                    "display_name": "DEP",
                    "type": "str",
                    "description": "Dependency label (e.g., nsubj, dobj)",
                    "default": ""
                },
                {
                    "name": "left_id",
                    "display_name": "Left ID",
                    "type": "str",
                    "description": "ID of the token this depends on",
                    "default": ""
                },
                {
                    "name": "rel_op",
                    "display_name": "Relation",
                    "type": "str",
                    "description": "Dependency relation operator (>, <, >>, <<)",
                    "default": ">"
                }
            ],
        ),
        BoolInput(
            name="include_details",
            display_name="Include Details",
            info="Include linguistic details in the results",
            value=True
        )
    ]

    outputs = [
        Output(display_name="Matches", name="matches", method="process_text"),
    ]

    def _convert_schema_to_patterns(self) -> Dict:
        """Convert table schema input into spaCy dependency patterns"""
        if not hasattr(self, 'pattern_schema') or not self.pattern_schema:
            return self._get_default_patterns()

        patterns = {}
        current_pattern = None
        current_rules = []

        for row in self.pattern_schema:
            pattern_name = row["pattern_name"]
            
            # Create a new pattern list if pattern name changes
            if current_pattern != pattern_name:
                if current_pattern and current_rules:
                    if current_pattern not in patterns:
                        patterns[current_pattern] = []
                    patterns[current_pattern].append(current_rules)
                current_pattern = pattern_name
                current_rules = []

            # Build rule from row
            rule = {
                "RIGHT_ID": row["right_id"],
                "RIGHT_ATTRS": {}
            }

            # Add POS if specified
            if row["pos"]:
                rule["RIGHT_ATTRS"]["POS"] = row["pos"]
            
            # Add DEP if specified
            if row["dep"]:
                rule["RIGHT_ATTRS"]["DEP"] = row["dep"]

            # Add relation information if this is a dependent token
            if row["left_id"]:
                rule["LEFT_ID"] = row["left_id"]
                rule["REL_OP"] = row["rel_op"]

            current_rules.append(rule)

        # Add the last pattern
        if current_pattern and current_rules:
            if current_pattern not in patterns:
                patterns[current_pattern] = []
            patterns[current_pattern].append(current_rules)

        return patterns

    def _get_default_patterns(self) -> Dict:
        """Default patterns to use if none are provided"""
        return {
            "ACTIVE_VOICE": [
                [
                    {
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {"POS": "VERB"}
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "subject",
                        "RIGHT_ATTRS": {"DEP": "nsubj"}
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "object",
                        "RIGHT_ATTRS": {"DEP": "dobj"}
                    }
                ]
            ],
            "PASSIVE_VOICE": [
                [
                    {
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {"POS": "VERB"}
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "subject",
                        "RIGHT_ATTRS": {"DEP": "nsubjpass"}
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "agent",
                        "RIGHT_ATTRS": {"DEP": "agent"}
                    }
                ]
            ]
        }

    def _get_match_info(self, doc: Doc, token_ids: List[int]) -> Dict:
        """Extract information about a found match"""
        info = {
            "text": " ".join(doc[i].text for i in token_ids),
            "tokens": [doc[i].text for i in token_ids],
            "span": doc[min(token_ids):max(token_ids) + 1].text
        }
        
        if self.include_details:
            info.update({
                "linguistic_info": {
                    "pos_tags": [doc[i].pos_ for i in token_ids],
                    "dep_labels": [doc[i].dep_ for i in token_ids],
                    "lemmas": [doc[i].lemma_ for i in token_ids]
                },
                "context": {
                    "sentence": str(doc[token_ids[0]].sent),
                    "start_char": doc[min(token_ids)].idx,
                    "end_char": doc[max(token_ids)].idx + len(doc[max(token_ids)].text)
                },
                "token_details": [
                    {
                        "text": doc[i].text,
                        "pos": doc[i].pos_,
                        "dep": doc[i].dep_,
                        "lemma": doc[i].lemma_,
                        "is_entity": bool(doc[i].ent_type_),
                        "entity_type": doc[i].ent_type_ if doc[i].ent_type_ else None
                    }
                    for i in token_ids
                ]
            })
        
        return info

    def process_text(self) -> List[Data]:
        """Process texts and identify syntactic patterns"""
        if not hasattr(self, 'data_inputs') or not self.data_inputs:
            raise ValueError("No input data provided")

        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")

        # Setup matcher with patterns from schema
        matcher = DependencyMatcher(self.spacy_model.vocab)
        patterns = self._convert_schema_to_patterns()

        # Add patterns to matcher
        for pattern_name, pattern_list in patterns.items():
            matcher.add(pattern_name, pattern_list)

        results = []
        for input_data in self.data_inputs:
            text = input_data.text if isinstance(input_data, Data) else str(input_data)
            doc = self.spacy_model(text)
            matches = matcher(doc)
            
            # Organize matches by pattern type
            matches_by_type = {}
            all_matches = []
            
            for match_id, token_ids in matches:
                pattern_name = doc.vocab.strings[match_id]
                match_info = self._get_match_info(doc, token_ids)
                
                if pattern_name not in matches_by_type:
                    matches_by_type[pattern_name] = []
                
                matches_by_type[pattern_name].append(match_info)
                all_matches.append({
                    "pattern": pattern_name,
                    **match_info
                })

            # Create formatted result
            processed_data = Data(
                text=text,
                data={
                    "text": text,
                    "matches": {
                        "by_pattern": matches_by_type,
                        "all": all_matches,
                        "statistics": {
                            "total_matches": len(matches),
                            "matches_per_pattern": {
                                pattern: len(matches)
                                for pattern, matches in matches_by_type.items()
                            }
                        }
                    },
                    "document_info": {
                        "sentences": len(list(doc.sents)),
                        "tokens": len(doc),
                        "entities": len(doc.ents)
                    },
                    "patterns_used": list(patterns.keys())
                }
            )
            results.append(processed_data)

        self.status = results
        return results

    def get_pattern_matches(self, pattern_name: str, max_examples: int = 3) -> List[Dict]:
        """Return examples of matches for a specific pattern"""
        if not hasattr(self, 'status'):
            return []

        examples = []
        for result in self.status:
            matches = result.data["matches"]["by_pattern"].get(pattern_name, [])
            examples.extend(matches[:max_examples])

        return examples[:max_examples]