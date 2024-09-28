# File: langflow/components/nlp/text_preprocessor.py

import re

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema.message import Message


class NaturalLanguageTextPreprocessorComponent(Component):
    display_name = "Text Preprocessor"
    description = "Preprocess text by removing special characters, digits, stopwords, and applying lemmatization."
    icon = "text"
    name = "TextPreprocessor"

    inputs = [
        DataInput(
            name="data_input",
            display_name="Input Text",
            info="The text data to be preprocessed.",
            input_types=["Data"],
        ),
        DataInput(
            name="stopwords_language",
            display_name="Stopwords Language",
            info='The language of stopwords. Default is "English".',
            value="English",
            input_types=["str"],
        ),
    ]

    outputs = [
        Output(display_name="Preprocessed Text", name="preprocessed_text", method="preprocess_text"),
    ]

    def preprocess_text(self) -> Message:
        try:
            input_data = self.data_input
            if hasattr(input_data, "text"):
                input_data = input_data.text

            text = input_data.lower()
            text = re.sub(r"[^a-zA-Z\s]", "", text)
            text = re.sub(r"\s+", " ", text)

            stop_words = set(stopwords.words(self.stopwords_language.lower()))
            word_tokens = word_tokenize(text)
            filtered_text = [word for word in word_tokens if word not in stop_words]
            text = " ".join(filtered_text)

            lemmatizer = WordNetLemmatizer()
            lemmatized_text = [lemmatizer.lemmatize(word) for word in word_tokenize(text)]
            text = " ".join(lemmatized_text)

            return Message(text=text)
        except Exception as e:
            return Message(text=f"Error: {str(e)}")
