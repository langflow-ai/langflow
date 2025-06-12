from pydantic import ValidationError

from langflow.base.data import BaseFileComponent
from langflow.schema import Data


class LoadDoclingDocumentComponent(BaseFileComponent):
    display_name = "Load DoclingDocument"
    description = "Load JSON files as DoclingDocument."
    documentation = "https://docling-project.github.io/docling/"
    trace_type = "tool"
    icon = "Docling"
    name = "LoadDoclingDocument"

    VALID_EXTENSIONS = [
        "json",
    ]

    inputs = [
        *BaseFileComponent._base_inputs,
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        from docling_core.types.doc import DoclingDocument

        processed_data: list[Data | None] = []
        for file in file_list:
            if file.path is None:
                processed_data.append(None)
                continue

            try:
                doc = DoclingDocument.load_from_json(filename=file.path)

                processed_data.append(
                    Data(
                        data={
                            "doc": doc,
                            # "text": doc.export_to_markdown(),
                            "file_path": str(file.path),
                        }
                    )
                )
            except ValidationError as e:
                self.log(f"Error loading document {file}: {e}")
                processed_data.append(None)

        return self.rollup_data(file_list, processed_data)
