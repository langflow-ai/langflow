from typing import Optional, Dict, Any
from langflow.base.models.model import LCModelComponent
from langflow.io import DropdownInput, BoolInput, Output
from langflow.schema.dotdict import dotdict
import spacy
from spacy.language import Language

class SpaCyModelComponent(LCModelComponent):
    display_name = "SpaCy Model"
    description = "Load and configure a SpaCy language model"
    icon = "languages"

    LANGUAGE_MODELS = {
        "English": ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"],
        "German": ["de_core_news_sm", "de_core_news_md", "de_core_news_lg"],
        "French": ["fr_core_news_sm", "fr_core_news_md", "fr_core_news_lg"],
        "Spanish": ["es_core_news_sm", "es_core_news_md", "es_core_news_lg"],
        "Portuguese": ["pt_core_news_sm", "pt_core_news_md", "pt_core_news_lg"],
        "Italian": ["it_core_news_sm"],
        "Dutch": ["nl_core_news_sm"],
        "Greek": ["el_core_news_sm"],
        "Norwegian": ["nb_core_news_sm"],
        "Lithuanian": ["lt_core_news_sm"],
        "Danish": ["da_core_news_sm"],
        "Polish": ["pl_core_news_sm"],
        "Japanese": ["ja_core_news_sm"],
        "Chinese": ["zh_core_web_sm"],
        "Romanian": ["ro_core_news_sm"],
        "Catalan": ["ca_core_news_sm"],
        "Croatian": ["hr_core_news_sm"],
        "Finnish": ["fi_core_news_sm"],
        "Korean": ["ko_core_news_sm"],
        "Russian": ["ru_core_news_sm"],
        "Swedish": ["sv_core_news_sm"],
        "Ukrainian": ["uk_core_news_sm"]
    }

    inputs = [
        DropdownInput(
            name="language",
            display_name="Language",
            info="The language of the model to load.",
            options=list(LANGUAGE_MODELS.keys()),
            value="English",
            refresh_button=True
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="SpaCy model to load",
            options=[],
            value=""
        ),
        BoolInput(
            name="merge_entities",
            display_name="Merge Entities",
            info="Whether to merge entity spans",
            value=True,
            advanced=True
        )
    ]

    outputs = [
        Output(display_name="SpaCy Model", name="model", method="load_model"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self._nlp: Optional[Language] = None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "language":
            build_config["model_name"]["options"] = self.LANGUAGE_MODELS.get(field_value, [])
            build_config["model_name"]["value"] = build_config["model_name"]["options"][0] if build_config["model_name"]["options"] else ""
        return build_config
    
    def load_model(self) -> Language:
        """Load and configure the SpaCy model."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self.model_name)
                if self.merge_entities:
                    if "merge_entities" not in self._nlp.pipe_names:
                        self._nlp.add_pipe("merge_entities")
                self.status = f"Loaded model {self.model_name}"
            except OSError:
                print(f"Downloading model {self.model_name}")
                spacy.cli.download(self.model_name)
                self._nlp = spacy.load(self.model_name)
                if self.merge_entities:
                    if "merge_entities" not in self._nlp.pipe_names:
                        self._nlp.add_pipe("merge_entities")
                self.status = f"Downloaded and loaded model {self.model_name}"
            except Exception as e:
                error_msg = f"Error loading SpaCy model: {str(e)}"
                self.status = error_msg
                raise ValueError(error_msg)
        
        return self._nlp
