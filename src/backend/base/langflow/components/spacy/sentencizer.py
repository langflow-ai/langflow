from langflow.custom import Component
from langflow.io import HandleInput, Output, BoolInput, MessageTextInput
from langflow.schema.message import Message
from langflow.schema import Data
from langflow.schema.dotdict import dotdict
from spacy.language import Language
from spacy.tokens import Doc
from collections import Counter
import re
from typing import Set, List, Any

class SpacySentencizerRAG(Component):
    display_name = "Sentencizer"
    description = "Segments and preprocesses text for RAG using spaCy's advanced models, with optional automatic abbreviation detection and punctuation recommendation."
    icon = "scissors"

    inputs = [
        HandleInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="The data to be segmented and preprocessed for RAG.",
            input_types=["Data"],
            is_list=True,
        ),
        HandleInput(
            name="spacy_model",
            display_name="SpaCy Model",
            info="SpaCy language model to use for processing",
            input_types=["Language"]
        ),
        BoolInput(
            name="auto_detect",
            display_name="Auto Detect",
            info="Automatically detect abbreviations and recommend punctuation.",
            value=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="punct_chars", 
            display_name="Punctuation Characters",
            info="Additional characters to consider as sentence endings (comma-separated).",
        ),
        MessageTextInput(
            name="abbreviations",
            display_name="Custom Abbreviations", 
            info="Custom abbreviations to consider (comma-separated, e.g., 'Mr., Mrs., Dr.').",
        ),
        BoolInput(
            name="overwrite",
            display_name="Overwrite Existing",
            info="Whether to overwrite existing segmentation.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="clean_text",
            display_name="Clean Text",
            info="Apply basic text cleaning (remove extra whitespace).",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="processed_text",
            display_name="Processed Text",
            method="process_text", 
        ),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self._fallback_patterns = [
            r'\b[A-Z][a-z]{0,2}\.\s+[A-Z][a-z]{0,2}\.',
            r'\b[A-Z]\.(?:[A-Z]\.)+[A-Z]?\.?',
            r'\b[A-Z][a-z]{1,3}\.',
            r',\s+[A-Z]\.[A-Z]\.(?:[A-Z]\.)*',
            r'\b[A-Z]{2,5}\.',
        ]

    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text).strip()

    def is_model_detected_abbreviation(self, token) -> bool:
        if not token.text.endswith('.'):
            return False

        return (
            (token.ent_type_ in {"ORG", "GPE"} and token.is_upper) or
            (token.pos_ == "PROPN" and (token.is_title or token.is_upper)) or
            (token.pos_ == "NOUN" and token.is_title and len(token.text) <= 4) or
            (token.is_upper and '.' in token.text[:-1]) or
            (all(c.isupper() or c == '.' for c in token.text) and 
             len(token.text.replace('.', '')) >= 2)
        )

    def apply_regex_patterns(self, text: str) -> Set[str]:
        abbreviations = set()
        for pattern in self._fallback_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                abbrev = match.group().strip()
                if ',' in abbrev:
                    abbrev = abbrev.split(',')[1].strip()
                if abbrev and abbrev != '.':
                    abbreviations.add(abbrev)
        return abbreviations

    def process_compound_tokens(self, doc: Doc) -> Set[str]:
        compounds = set()
        for i in range(len(doc) - 1):
            current = doc[i]
            next_token = doc[i + 1]
            
            if (current.text.endswith('.') and 
                next_token.text.endswith('.') and
                current.is_title and 
                next_token.is_title):
                
                compound = f"{current.text} {next_token.text}"
                if len(compound) <= 8:
                    compounds.add(compound)
        
        return compounds

    def detect_abbreviations(self, doc: Doc) -> Set[str]:
        all_abbreviations: Set[str] = set()
        
        compounds = self.process_compound_tokens(doc)
        all_abbreviations.update(compounds)

        for token in doc:
            if self.is_model_detected_abbreviation(token):
                abbrev = token.text if token.text.endswith('.') else f"{token.text}."
                if abbrev != "." and len(abbrev) > 1:
                    all_abbreviations.add(abbrev)

        regex_abbreviations = self.apply_regex_patterns(doc.text)
        all_abbreviations.update(regex_abbreviations)

        return {abbr.strip() for abbr in all_abbreviations if abbr.strip() and abbr.strip() != "."}

    def analyze_punctuation(self, doc: Doc) -> Counter:
        punctuation_counter = Counter()
        for token in doc:
            if token.is_punct and token.is_sent_end:
                punctuation_counter[token.text] += 1
        return punctuation_counter

    def recommend_punctuation(self, doc: Doc) -> List[str]:
        punctuation_counts = self.analyze_punctuation(doc)
        return [punct for punct, _ in punctuation_counts.most_common(3)]

    def process_text(self) -> list[Data]:
        if not isinstance(self.spacy_model, Language):
            raise ValueError("Invalid SpaCy model. Please connect a valid SpaCy Model component.")

        if not self.data_inputs or not isinstance(self.data_inputs[0], Data):
            return []
            
        text = self.data_inputs[0].text
        
        text = self.clean_text(text) if self.clean_text else text
        custom_abbrev = [abbr.strip() for abbr in self.abbreviations.split(',')] if self.abbreviations else []
        
        if custom_abbrev:
            for abbr in custom_abbrev:
                text = text.replace(abbr, abbr.replace('.', '@'))
        
        if "sentencizer" not in self.spacy_model.pipe_names:
            sentencizer = self.spacy_model.add_pipe("sentencizer", before="parser")
        else:
            sentencizer = self.spacy_model.get_pipe("sentencizer")

        if self.punct_chars:
            punct_chars = set(char.strip() for char in self.punct_chars.split(','))
            sentencizer.punct_chars.update(punct_chars)
        
        sentencizer.overwrite = self.overwrite
        
        doc = self.spacy_model(text)

        if self.auto_detect:
            detected_abbrev = self.detect_abbreviations(doc)
            custom_abbrev.extend(detected_abbrev)
            recommended_punct = self.recommend_punctuation(doc)
            if recommended_punct:
                sentencizer.punct_chars.update(recommended_punct)

        sentences = [sent.text.strip() for sent in doc.sents]
        
        processed_sentences = []
        for sent in sentences:
            if custom_abbrev:
                for abbr in custom_abbrev:
                    sent = sent.replace(abbr.replace('.', '@'), abbr)
            processed_sentences.append(sent)

        final_sentences = []
        current_sentence = ""
        in_quotes = False
        for sent in processed_sentences:
            if '"' in sent:
                if in_quotes:
                    current_sentence += " " + sent
                    if sent.count('"') % 2 == 1:
                        final_sentences.append(current_sentence)
                        current_sentence = ""
                        in_quotes = False
                else:
                    if current_sentence:
                        final_sentences.append(current_sentence)
                    current_sentence = sent
                    if sent.count('"') % 2 == 0:
                        final_sentences.append(current_sentence)
                        current_sentence = ""
                    else:
                        in_quotes = True
            else:
                if in_quotes:
                    current_sentence += " " + sent
                else:
                    if current_sentence:
                        final_sentences.append(current_sentence)
                    current_sentence = sent
        
        if current_sentence:
            final_sentences.append(current_sentence)

        sentences_to_process = final_sentences if final_sentences else processed_sentences
        data_list = [Data(text=sent) for sent in sentences_to_process]
        
        self.status = data_list
        return data_list

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "auto_detect":
            if field_value:
                # Hide manual inputs when auto_detect is True
                build_config["punct_chars"]["show"] = False
                build_config["abbreviations"]["show"] = False
            else:
                # Show manual inputs when auto_detect is False
                build_config["punct_chars"]["show"] = True
                build_config["abbreviations"]["show"] = True
        return build_config
