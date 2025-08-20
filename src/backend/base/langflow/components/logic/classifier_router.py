import heapq
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

import numpy as np
from langchain.callbacks.base import BaseCallbackHandler
from langchain.evaluation.embedding_distance import (
    EmbeddingDistance,
    EmbeddingDistanceEvalChain,
)
from langchain_core.prompts import PromptTemplate
from typing_extensions import override

from langflow.components.processing.structured_output import StructuredOutputComponent
from langflow.custom.custom_component.component import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.helpers.data import data_to_text
from langflow.inputs.inputs import (
    BoolInput,
    FloatInput,
    InputTypes,
    IntInput,
    MultilineInput,
)
from langflow.io import DropdownInput, HandleInput, MessageInput, MessageTextInput, Output, TabInput, TableInput
from langflow.logging import logger
from langflow.memory import aget_messages
from langflow.schema import Data
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from langflow.utils.async_helpers import run_until_complete

CLASSIFIER_PROMPT = """
# Task Description
You are a text classification engine that analyzes user input and dialogue history to assign exactly one category from a given list.

### Objective
- Assign **only one category** to the input text.  
- Extract **keywords** from the input text that are relevant to the classification.  
- If the user responds briefly (e.g., "yes", "no", "1", "let’s continue"), treat it as a continuation of the dialogue and classify it in the context of the ongoing conversation.  
- Provide a **confidence score** between 0.00 and 1.00 (step 0.01) under the `"confidence"` field.

### Input Format
- User message is given in `input_text`.  
- List of available categories is provided in `categories`.  
- Descriptions of categories are provided in `descriptions`.  
- Additional classification instructions may appear in `classification_instruction`.

### Output Format
- Return **only a JSON object**, no extra text or explanations.  

### Example
<example>
User:{{
    "input_text": [
        "Tell me how the movie Titanic was filmed. Who was the director and what rare facts do you know?"
    ],
    "categories": [
        {{
            "name": "Football",
            "description":"Everything about football, football equipment and players"
        }},
        {{
            "name": "Cinema",
            "description":"Everything about movies and film production"
        }},
        {{
            "name": "Music",
            "description":"Everything about music and musicians"
        }}
    ],
    "classification_instruction" : []
}}
Assistant:{{
    "keywords": ["Titanic", "movie", "filmed", "director", "rare facts"],
    "category_name": "Cinema",
    "confidence": 0.98
}}
</example>

<example>
User:{{
    "input_text": [
        "What’s the weather like in St. Petersburg?"
    ],
    "categories": [
        {{
            "name": "Football",
            "description":"Everything about football, football equipment and players"
        }},
        {{
            "name": "Cinema",
            "description":"Everything about movies and film production"
        }},
        {{
            "name": "Music",
            "description":"Everything about music and musicians"
        }}
    ],
    "classification_instruction" : ["Use only the given categories"]
}}
Assistant:{{
    "keywords": ["weather", "St. Petersburg"],
    "category_name": null,
    "confidence": 0.00
}}
</example>
### End of Examples

## Dialogue History
Here is the dialogue history inside XML tags <histories></histories>.  
If the user provides a short reply (e.g., "yes", "no", "1", "continue", "okay"), this means it is a continuation of the previous topic. In that case, the classification must remain in the same category as the last relevant user question.

<histories>
{histories}
</histories>

# START OF USER INPUT

##User:
{{
    "input_text" : ["{input_text}"],
    "categories" : {categories},
    "classification_instruction" : ["Use only the given categories, no others"]
}}
##Assistant:
"""


class ClassifierType(Enum):
    EMBEDDING = "Embedding"
    LLM = "LLM"


@dataclass
class EmbeddingClassifier:
    fields = [
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            required=True,
        ),
        FloatInput(
            name="distance_threshold",
            display_name="Distance threshold",
            info="0.0 is a full match",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
            value=0.19,
        ),
        IntInput(
            name="top_n_values",
            display_name="Top N",
            info="The number of elements whose similarity is close to input_text and whose similarity value exceeds distance_threshold.",
            advanced=True,
            value=1,
        ),
        DropdownInput(
            name="distance_metric",
            display_name="Distance metric",
            info="The distance metric to use for comparing the embeddings",
            options=[member.value for member in EmbeddingDistance],
            advanced=True,
            value=EmbeddingDistance.COSINE,
        ),
    ]
    embedding: Any
    input_text: str
    categories_descriptions: list[dict[str, str]]
    distance_threshold: float = 0.19
    top_n_values: int = 1
    distance_metric: EmbeddingDistance = EmbeddingDistance.COSINE
    input_text_embedded: np.ndarray | None = field(default=None, init=False)
    embeded_values: dict[str, np.ndarray] = field(default_factory=dict, init=False)
    similarities: dict[str, float] = field(default_factory=dict, init=False)
    top_n_values_name: list[str] = field(default_factory=list, init=False)

    def initialize_embeddings(self):
        self.input_text_embedded = np.array(self.embedding.embed_query(self.input_text))
        for value in self.categories_descriptions:
            self._add_value_to_embedding_dict(value["category"], value["description"])

    def _add_value_to_embedding_dict(self, key: str, value: str) -> None:
        if key not in self.embeded_values:
            self.embeded_values[key] = np.array(self.embedding.embed_query(value))

    def calculate_distance(self):
        ed = EmbeddingDistanceEvalChain(embeddings=self.embedding, distance_metric=self.distance_metric)
        self.similarities = {}
        for k, v in self.embeded_values.items():
            distance = ed._compute_score(np.array([self.input_text_embedded, v]))
            logger.debug(f"Embeded distance ({k}): {distance}")
            if distance < self.distance_threshold:
                self.similarities[k] = distance
        self.top_n_values_name = [
            k for k, _ in heapq.nsmallest(self.top_n_values, self.similarities.items(), key=lambda x: x[1])
        ]
        logger.info(f"Top {self.top_n_values} similar categories: {self.top_n_values_name}")


@dataclass
class LLMClassifier:
    fields = [
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
        ),
        BoolInput(
            name="use_with_structured_output",
            display_name="Use structured output for classifier",
            advanced=True,
            info="If true, LLM will answer using with_structured_output option",
            value=False,
        ),
        MultilineInput(
            name="classifier_prompt",
            display_name="Classifier Prompt",
            info="Prompt for classifier",
            advanced=True,
            value=CLASSIFIER_PROMPT,
        ),
        BoolInput(
            name="use_history",
            display_name="Use history",
            advanced=True,
            info="If true, history will be used for context",
            value=True,
        ),
        FloatInput(
            name="confidence_threshold",
            display_name="Confidence",
            info="Confidence level from 0.00 to 1.00",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
            value=0.8,
        ),
    ]
    llm: Any
    input_text: str
    categories_descriptions: list[dict[str, str]]
    classifier_prompt: str
    callbacks: list[BaseCallbackHandler]
    use_with_structured_output: bool = False
    use_history: bool = True
    confidence_threshold: float = 0.81
    graph_session_id: str | None = None
    project_name: str | None = None
    run_id: str | None = None

    structured_output: StructuredOutputComponent = field(default_factory=StructuredOutputComponent, init=False)
    top_n_values_name: list[str] = field(default_factory=list, init=False)

    def get_structured_output(self, prompt_value: str) -> tuple:
        self.structured_output.output_schema = [
            {
                "name": "keywords",
                "description": "the key words from the text that are related to the classification",
                "type": "text",
                "multiple": True,
            },
            {"name": "category_name", "description": "Assigned category", "type": "text", "multiple": False},
            {
                "name": "confidence",
                "description": "Indication the confidence level in the correctness of the chosen category. The confidence level is a float from 0.00 to 1.00.",
                "type": "float",
                "multiple": False,
            },
        ]
        self.structured_output.set(
            llm=self.llm,
            schema_name="result",
            description="classification",
            display_name="Classifier",
            multiple=False,
            input_value=prompt_value,
        )
        df = self.structured_output.build_structured_dataframe()
        best_row = df.sort_values(by="confidence", ascending=False).iloc[0]
        return best_row["category_name"], best_row["confidence"]

    def get_raw_output(self, prompt_value: str) -> tuple[str, float]:
        runnable = self.llm.with_config(
            {
                "run_name": "Classifier",
                "project_name": self.project_name,
                "callbacks": self.callbacks,
                "run_id": self.run_id,
            }
        )
        message = runnable.invoke(prompt_value)
        chat_result = getattr(message, "content", message)
        try:
            data = json.loads(chat_result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM JSON: {e}")
            return "", 0.0
        return data.get("category_name", ""), data.get("confidence", 0.0)

    def process_result(self):
        try:
            prompt_value = self._build_prompt_value()

            if self.use_with_structured_output:
                try:
                    category_name, confidence = self.get_structured_output(prompt_value)
                    logger.debug("Structured output used success")
                except Exception as ex:
                    logger.warning(f"Error while get structured output: {ex}. Try to get json from raw data")
                    category_name, confidence = self.get_raw_output(prompt_value)
            else:
                category_name, confidence = self.get_raw_output(prompt_value)
            logger.debug(f"{category_name=}, {confidence=}")
            if self._is_confident_match(category_name, confidence):
                self.top_n_values_name.append(category_name)
        except Exception as e:
            logger.error(f"Unexpected error in _llm_result: {e}")

    def _build_prompt_value(self) -> str:
        prompt = PromptTemplate.from_template(self.classifier_prompt)
        return prompt.invoke(
            {
                "histories": self._get_memory_data(),
                "input_text": self.input_text,
                "categories": [
                    {"name": v["category"], "description": v["description"]} for v in self.categories_descriptions
                ],
            }
        ).to_string()

    def _is_confident_match(self, category_name: str, confidence: float) -> bool:
        categories = [v["category"] for v in self.categories_descriptions]
        return confidence > self.confidence_threshold and category_name in categories

    def _get_memory_data(self) -> str:
        if not self.use_history:
            return ""

        result = run_until_complete(self._async_get_memory_data())
        return result or ""

    async def _async_get_memory_data(self) -> str:
        stored = await aget_messages(
            session_id=self.graph_session_id,
            sender_name=None,
            sender=None,
            limit=10,
            order="DESC",
        )
        stored.reverse()
        return data_to_text("{sender_name}: {text}", cast(Data, stored))


class ClassifierRouterComponent(Component):
    display_name = "Classifier router"
    description = "Route income message by variant categories"
    icon = "split"
    name = "Classifier Routing"
    beta: bool = True

    inputs = [
        TabInput(
            name="classifier_type",
            display_name="Classifier type",
            info="Chose between Embedding and LLM methods to classify query",
            options=[member.value for member in ClassifierType],
            value=ClassifierType.LLM.value,
            real_time_refresh=True,
        ),
        TableInput(
            name="categories_descriptions",
            display_name="Categories",
            info="Define categories and its descriptions",
            refresh_button=True,
            real_time_refresh=True,
            table_schema=[
                {
                    "name": "category",
                    "display_name": "Category",
                    "type": "str",
                    "description": "Name of category",
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the category.",
                },
            ],  # type: ignore
            value=[],
        ),
        MessageTextInput(
            name="input_text",
            display_name="Text Input",
            info="The primary text input for the operation.",
            required=True,
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The message to pass through either route. If null, then Text Input used",
            advanced=True,
        ),
        *LLMClassifier.fields,
    ]

    outputs = [
        Output(display_name="no matches", name="no_matches", method="no_matches_response", group_outputs=True),
    ]

    def __init__(self, **kwargs) -> None:
        parameters = kwargs.get("_parameters", {})
        try:
            categories: list[str] = [value[0] for value in parameters.get("categories_descriptions").values]
        except:
            categories = []

        self.embedding_classifier = None
        self.llm_classifier = None
        self.top_n_values_name: list[str] = []

        if categories:
            self._initialize_outputs(categories)
        super().__init__(**kwargs)

    def _initialize_outputs(self, categories: list[str]) -> None:
        for value in categories:
            setattr(self, f"_check_{value}", self.base_check(value))
        self.outputs += [
            Output(display_name=value, name=value, method=f"_check_{value}", group_outputs=True) for value in categories
        ]

    def base_check(self, value) -> Callable:
        def check() -> Message:
            if value in self.top_n_values_name:
                return self.message if self.message.text else self.input_text
            self.stop(value)
            logger.debug(f"stop output '{value}'")
            return None  # type: ignore

        return check

    def no_matches_response(self) -> Message:
        if not self.top_n_values_name:
            return self.message if self.message.text else self.input_text
        self.stop("no_matches")
        return None  # type: ignore

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:  # noqa: ARG002
        self.categories_descriptions: list[dict[str, str]]
        categories = []
        additional_outputs = []
        for value in self.categories_descriptions:
            category = value["category"]
            if category:
                categories.append(category)
                additional_outputs.append(
                    {
                        "types": ["Message"],
                        "selected": "Message",
                        "name": category,
                        "display_name": category,
                        "method": f"_check_{category}",
                        "value": "__UNDEFINED__",
                        "cache": True,
                        "group_outputs": True,
                    }
                )

        self._initialize_outputs(categories=categories)
        frontend_node["outputs"] += additional_outputs
        return frontend_node

    @override
    def set_attributes(self, params: dict) -> None:
        super().set_attributes(params)

        if hasattr(self, "embedding") and self.embedding:
            self.embedding_classifier = EmbeddingClassifier(
                embedding=self.embedding,
                input_text=self.input_text,
                categories_descriptions=self.categories_descriptions,
                distance_threshold=self.distance_threshold,
                top_n_values=self.top_n_values,
                distance_metric=self.distance_metric,
            )
            self.embedding_classifier.initialize_embeddings()
            self.embedding_classifier.calculate_distance()
            self.top_n_values_name = self.embedding_classifier.top_n_values_name

        if hasattr(self, "llm") and self.llm:
            self.llm_classifier = LLMClassifier(
                llm=self.llm,
                input_text=self.input_text,
                categories_descriptions=self.categories_descriptions,
                classifier_prompt=self.classifier_prompt,
                callbacks=self.get_langchain_callbacks(),
                use_with_structured_output=self.use_with_structured_output,
                use_history=self.use_history,
                confidence_threshold=self.confidence_threshold,
                graph_session_id=self.graph.session_id,
                project_name=self.get_project_name(),
                run_id=self.graph.run_id,
            )
            self.llm_classifier.structured_output._tracing_service = self._tracing_service
            self.llm_classifier.process_result()
            self.top_n_values_name = self.llm_classifier.top_n_values_name

    def _delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        for field in fields:
            build_config.pop(field, None)

    @staticmethod
    def _get_model(fileds_list: list[InputTypes]) -> dict[str | None, dict[str, Any]]:
        return {_input.name: _input.model_dump(by_alias=True, exclude_none=True) for _input in fileds_list}

    def update_build_config(self, build_config: dotdict, field_value: str, field_name: str | None = None) -> dotdict:
        embeding_inputs = self._get_model(EmbeddingClassifier.fields)
        llm_inputs = self._get_model(LLMClassifier.fields)
        if field_name == "classifier_type":
            if field_value == ClassifierType.LLM.value:
                self._delete_fields(build_config, embeding_inputs)
                build_config.update(llm_inputs)
            elif field_value == ClassifierType.EMBEDDING.value:
                self._delete_fields(build_config, llm_inputs)
                build_config.update(embeding_inputs)
            else:
                msg = "Invalid classifier type"
                raise ValueError(msg)

        return build_config
