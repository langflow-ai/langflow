from docling_core.types.doc import DoclingDocument

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


def extract_docling_documents(data_inputs: Data | list[Data] | DataFrame, doc_key: str) -> list[DoclingDocument]:
    documents: list[DoclingDocument] = []
    if isinstance(data_inputs, DataFrame):
        if not len(data_inputs):
            msg = "DataFrame is empty"
            raise TypeError(msg)

        if doc_key not in data_inputs.columns:
            msg = f"Column '{doc_key}' not found in DataFrame"
            raise TypeError(msg)
        try:
            documents = data_inputs[doc_key].tolist()
        except Exception as e:
            msg = f"Error extracting DoclingDocument from DataFrame: {e}"
            raise TypeError(msg) from e
    else:
        if not data_inputs:
            msg = "No data inputs provided"
            raise TypeError(msg)

        if isinstance(data_inputs, Data):
            if doc_key not in data_inputs.data:
                msg = f"{doc_key} field not available in the input Data"
                raise TypeError(msg)
            documents = [data_inputs.data[doc_key]]
        else:
            try:
                documents = [
                    input_.data[doc_key]
                    for input_ in data_inputs
                    if isinstance(input_, Data)
                    and doc_key in input_.data
                    and isinstance(input_.data[doc_key], DoclingDocument)
                ]
                if not documents:
                    msg = f"No valid Data inputs found in {type(data_inputs)}"
                    raise TypeError(msg)
            except AttributeError as e:
                msg = f"Invalid input type in collection: {e}"
                raise TypeError(msg) from e
    return documents
