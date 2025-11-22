from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from lfx.base.data.utils import TEXT_FILE_TYPES
from lfx.custom.custom_component.component import Component
from lfx.helpers.data import safe_convert
from lfx.io import (
    BoolInput,
    DropdownInput,
    FileInput,
    HandleInput,
    MessageTextInput,
    MultilineInput,
    Output,
    TableInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.table import EditMode


class LangExtractComponent(Component):
    """Single-node integration for the LangExtract library.

    Features:
    - Structured extraction with character-level grounding (offset metadata).
    - Optional HTML visualization with highlights/citations.
    - Works with Gemini and other providers supported by LangExtract.
    """

    display_name = "LangExtract"
    description = "Structured extraction with grounding and optional HTML highlights using LangExtract."
    documentation = "https://langextract.com"
    icon = "Highlighter"
    name = "LangExtract"
    trace_type = "tool"

    inputs = [
        MultilineInput(
            name="input_text",
            display_name="Input Text",
            info="Texto simples para extrair. Você pode combinar com arquivos ou Documents.",
            advanced=False,
        ),
        FileInput(
            name="files",
            display_name="Files",
            info="Arquivos de texto (ou PDF/Office já convertidos) para extrair.",
            file_types=TEXT_FILE_TYPES,
            is_list=True,
            temp_file=True,
            advanced=True,
        ),
        HandleInput(
            name="documents",
            display_name="Documents",
            info="Entrada alternativa (Data, Message ou lista) cujo conteúdo será convertido em texto.",
            input_types=["Data", "Message", "Text"],
            is_list=True,
            required=False,
            advanced=True,
        ),
        MultilineInput(
            name="prompt_description",
            display_name="Prompt / Description",
            info="Instruções de extração. Ex.: 'Extraia pessoas, organizações e locais.'",
            required=True,
        ),
        MessageTextInput(
            name="example_text",
            display_name="Example Text",
            info="Texto de exemplo para treinar a extração. Combine com a tabela de extrações abaixo.",
            advanced=False,
        ),
        TableInput(
            name="examples_table",
            display_name="Extractions (Table)",
            info="Preencha pares classe/extração; todas as linhas usam o mesmo Example Text acima.",
            table_schema=[
                {
                    "name": "extraction_class",
                    "display_name": "Class",
                    "type": "str",
                    "description": "Nome da classe/campo a extrair.",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "extraction_text",
                    "display_name": "Extraction",
                    "type": "str",
                    "description": "Texto que deveria ser extraído.",
                    "edit_mode": EditMode.POPOVER,
                },
            ],
            value=[{"extraction_class": "", "extraction_text": ""}],
            advanced=False,
        ),
        DropdownInput(
            name="model_id",
            display_name="Model",
            info="Modelos Google Gemini mais recentes (pode digitar outro ID manualmente).",
            options=[
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-3-pro-preview",
                "gemini-flash-latest",
                "gemini-flash-lite-latest",
                "gemini-2.5-flash-lite",
                "models/gemini-2.5-flash-lite",
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
            ],
            combobox=True,
            value="gemini-2.5-flash",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="api_key",
            display_name="API Key",
            info="Chave do provider (Google, OpenAI, OpenRouter etc.).",
            required=False,
            show=True,
            advanced=False,
        ),
        BoolInput(
            name="return_html",
            display_name="Generate HTML",
            info="Gera visualização com highlights/citações.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="structured_output",
            display_name="Structured Output",
            method="build_structured_output",
        ),
        Output(
            name="html_output",
            display_name="HTML Visualization",
            method="build_html_output",
        ),
    ]

    _cached_result: Any | None = None
    _cached_html: str | None = None

    # --- helpers ---------------------------------------------------------
    def _ensure_langextract(self):
        try:
            import langextract as lx
        except ImportError as e:  # pragma: no cover - import guard
            msg = (
                "LangExtract não está instalado. Instale com `uv pip install langextract` ou `pip install langextract`."
            )
            raise ImportError(msg) from e
        return lx

    def _gather_text(self) -> str:
        parts: list[str] = []

        # Table-driven input takes precedence if filled
        table = getattr(self, "input_table", None)
        if table and isinstance(table, list) and table:
            first_row = table[0] or {}
            if isinstance(first_row, dict):
                txt = first_row.get("text") or ""
                if txt:
                    parts.append(str(txt))

        # Legacy direct text (kept for backwards compatibility if passed via kwargs)
        if getattr(self, "input_text", None):
            parts.append(self.input_text)

        if self.files:
            files = self.files if isinstance(self.files, list) else [self.files]
            for f in files:
                try:
                    path = Path(f)
                    if path.exists():
                        parts.append(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError as exc:  # pragma: no cover - defensive
                    logger.debug(f"Failed to read file {f}: {exc}")

        docs = self.documents
        if docs:
            if not isinstance(docs, list):
                docs = [docs]
            for doc in docs:
                try:
                    parts.append(safe_convert(doc, clean_data=True))
                except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                    logger.debug(f"Fallback to str(doc) during conversion: {exc}")
                    parts.append(str(doc))

        text = "\n\n".join(p for p in parts if p).strip()
        if not text:
            msg = "Forneça 'Input Text' ou conecte 'Documents'."
            raise ValueError(msg)
        return text

    def _parse_examples(self) -> Any | None:
        """Parse examples: prefer Example Text + Extractions table; fallback to JSON legacy."""
        lx = self._ensure_langextract()
        example_data_cls = lx.data.ExampleData
        extraction_cls = lx.data.Extraction

        # 1) Table path: use example_text (preferred) or last gathered text as the common anchor
        table_rows = getattr(self, "examples_table", None)
        if isinstance(table_rows, list):
            anchor_text = (getattr(self, "example_text", None) or getattr(self, "_last_text", None) or "").strip()
            extractions: list[Any] = []
            for row in table_rows:
                if not isinstance(row, dict):
                    continue
                cls = (row.get("extraction_class") or "").strip()
                txt = (row.get("extraction_text") or "").strip()
                if not cls or not txt:
                    continue
                extractions.append(extraction_cls(extraction_class=cls, extraction_text=txt))
            if extractions and anchor_text:
                return [example_data_cls(text=anchor_text, extractions=extractions)]

        # 2) Fallback to JSON (legacy)
        examples_json = getattr(self, "examples_json", None)
        if examples_json in (None, "", "[]"):
            return None

        if isinstance(examples_json, (list, dict)):
            parsed = examples_json
        elif isinstance(examples_json, str):
            raw = examples_json.strip()
            if raw in ("", "[]"):
                return None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    from json_repair import repair_json

                    parsed = json.loads(repair_json(raw))
                except Exception as e:
                    msg = "Examples (JSON) precisa ser um JSON válido (lista ou objeto)."
                    raise ValueError(msg) from e
        else:
            msg = "Examples (JSON) precisa ser um JSON válido (lista ou objeto)."
            raise TypeError(msg)

        parsed_list = [parsed] if isinstance(parsed, dict) else parsed
        examples: list[Any] = []
        for item in parsed_list:
            if hasattr(item, "extractions"):
                examples.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("document") or item.get("input")
            ex_list = item.get("extractions") or item.get("labels") or item.get("examples")
            if not text or not ex_list:
                continue
            built = []
            for ex in ex_list:
                if hasattr(ex, "extraction_class") and hasattr(ex, "extraction_text"):
                    built.append(ex)
                    continue
                if not isinstance(ex, dict):
                    continue
                cls = ex.get("extraction_class") or ex.get("label") or ex.get("class")
                txt = ex.get("extraction_text") or ex.get("text") or ex.get("value")
                if cls and txt:
                    built.append(extraction_cls(extraction_class=cls, extraction_text=txt))
            if built:
                examples.append(example_data_cls(text=text, extractions=built))

        if not examples:
            msg = (
                "Examples são obrigatórios: preencha Example Text + Extractions (Table) ou use JSON com 'text' e "
                "'extraction_class'/'extraction_text'."
            )
            raise ValueError(msg)

        return examples

    def _result_to_dict(self, result: Any) -> Any:
        # Try common serialization paths used by LangExtract (pydantic models)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "dict"):
            return result.dict()
        if hasattr(result, "__dict__"):
            return result.__dict__
        return result

    def _run_extract(self):
        if self._cached_result is not None:
            return self._cached_result

        lx = self._ensure_langextract()
        text = self._gather_text()
        self._last_text = text  # store for examples fallback
        examples = self._parse_examples()

        kwargs = {
            "text_or_documents": text,
            "prompt_description": self.prompt_description,
        }
        if examples:
            kwargs["examples"] = examples
        if self.model_id:
            kwargs["model_id"] = self.model_id
        if self.api_key:
            kwargs["api_key"] = self.api_key

        result = lx.extract(**kwargs)
        self._cached_result = result
        return result

    # --- outputs ---------------------------------------------------------
    def build_structured_output(self) -> Data:
        result = self._run_extract()
        result_dict = self._result_to_dict(result)
        self.status = "Extraction finished"
        return Data(data=result_dict)

    def build_html_output(self) -> Data:
        if not self.return_html:
            return Data(data=None)
        if self._cached_html is not None:
            return Data(data={"html": self._cached_html})

        lx = self._ensure_langextract()
        result = self._run_extract()

        # Save annotated docs to a temp file, then generate HTML
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.jsonl"
            try:
                lx.io.save_annotated_documents([result], output_name=str(output_path))
            except (TypeError, ValueError):  # pragma: no cover - fallback if API differs
                lx.io.save_annotated_documents(result, output_name=str(output_path))

            html = lx.visualize(str(output_path))

        self._cached_html = html
        return Data(data={"html": html})
