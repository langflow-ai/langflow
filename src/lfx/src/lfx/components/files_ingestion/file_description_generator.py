"""Component that runs OpenDsStar's docling-based ingestion to generate file descriptions.

Takes file data from a Read File component, runs the full ingestion pipeline
(docling convert -> markdown shorten -> LLM describe) in a subprocess to avoid
memory issues, and outputs Data objects suitable for feeding into any Langflow
vector store component.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import traceback
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, IntInput, Output, StrInput
from lfx.schema.data import Data
from lfx.schema.message import Message


def _dbg(msg: str) -> None:
    """Write debug message to stderr so it always appears in the terminal."""
    sys.stderr.write(f"[FileDescriptionGeneratorComponent] {msg}\n")
    sys.stderr.flush()


class FileDescriptionGeneratorComponent(Component):
    display_name = "File Description Generator"
    description = (
        "Runs OpenDsStar docling-based ingestion to generate searchable file descriptions. "
        "Connect output to a vector store's Ingest Data input."
    )
    icon = "file-search"
    name = "FileDescriptionGeneratorComponent"

    inputs = [
        HandleInput(
            name="file_data",
            display_name="File Data",
            input_types=["Data", "DataFrame", "Message"],
            is_list=True,
            info="Output from a Read File component.",
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            info="LLM used to generate file descriptions.",
        ),
        StrInput(
            name="cache_dir",
            display_name="Cache Directory",
            value="./opendsstar_cache",
            info="Directory for caching docling analysis and LLM descriptions.",
            advanced=True,
        ),
        StrInput(
            name="embedding_model",
            display_name="Embedding Model",
            value="ibm-granite/granite-embedding-english-r2",
            info="Embedding model name (used only for cache keying, not for actual embedding).",
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            value=8,
            info="Number of files to process in each LLM batch.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Descriptions",
            name="descriptions",
            method="generate_descriptions",
        ),
    ]

    def _serialize_llm(self) -> dict:
        """Serialize the LLM model for passing to a subprocess."""
        from lfx.base.data.docling_utils import _serialize_pydantic_model

        return _serialize_pydantic_model(self.llm)

    def generate_descriptions(self) -> list[Data]:
        _dbg("========== generate_descriptions CALLED ==========")

        try:
            from lfx.schema.dataframe import DataFrame

            _dbg(f"self.file_data type: {type(self.file_data).__name__}")
            _dbg(f"self.file_data length: {len(self.file_data)}")
            _dbg(f"self.file_data repr: {self.file_data!r}")

            # Extract file paths from inputs.
            # DataFrames/Tables have file_path as a column; Data objects use the "file_path" key.
            file_paths: list[str] = []
            for i, item in enumerate(self.file_data):
                _dbg(f"  item[{i}] type: {type(item).__name__}")
                if isinstance(item, DataFrame):
                    # First try attrs (legacy), then check for file_path column
                    fp = item.attrs.get("source_file_path", "")
                    if fp:
                        _dbg(f"  item[{i}] DataFrame source_file_path from attrs={fp!r}")
                        file_paths.append(str(Path(fp)))
                    elif "file_path" in item.columns and not item.empty:
                        # Extract unique file paths from the file_path column
                        unique_paths = item["file_path"].dropna().unique().tolist()
                        _dbg(f"  item[{i}] DataFrame found {len(unique_paths)} file_path(s) in column")
                        file_paths.extend(str(Path(path)) for path in unique_paths if path)
                    else:
                        _dbg(
                            f"  WARNING: item[{i}] DataFrame has no source_file_path"
                            " in attrs or file_path column, skipping"
                        )
                elif isinstance(item, Message):
                    fp = getattr(item, "file_path", "") or ""
                    _dbg(f"  item[{i}] Message file_path={fp!r}")
                    if fp:
                        file_paths.append(str(Path(fp)))
                    else:
                        _dbg(f"  WARNING: item[{i}] Message has no file_path, skipping")
                elif isinstance(item, Data):
                    fp = item.data.get("file_path", "")
                    _dbg(f"  item[{i}] Data file_path={fp!r}")
                    if fp:
                        file_paths.append(str(Path(fp)))
                    else:
                        _dbg(f"  WARNING: item[{i}] Data has no file_path key, skipping")
                else:
                    _dbg(f"  WARNING: item[{i}] unsupported type {type(item).__name__}, skipping")

            _dbg(f"Extracted file_paths: {file_paths}")

            if not file_paths:
                _dbg("NO FILE PATHS FOUND - returning empty list")
                return []

            _dbg(f"Processing {len(file_paths)} file(s) in subprocess...")

            # Serialize LLM
            _dbg(f"LLM type: {type(self.llm).__name__}")
            _dbg("Serializing LLM...")
            llm_config = self._serialize_llm()
            _dbg(f"LLM serialized, class_path: {llm_config.get('__class_path__', 'unknown')}")

            config = {
                "file_paths": file_paths,
                "llm_config": llm_config,
                "cache_dir": self.cache_dir,
                "embedding_model": self.embedding_model,
                "batch_size": self.batch_size,
            }

            _dbg(f"Config keys: {list(config.keys())}")
            _dbg(f"cache_dir: {self.cache_dir}")
            _dbg(f"embedding_model: {self.embedding_model}")
            _dbg(f"batch_size: {self.batch_size}")
            _dbg("Launching subprocess...")

            # Run the entire ingestion in a single subprocess over all files
            script = textwrap.dedent("""\
                import json
                import sys
                import logging
                from pathlib import Path

                logging.basicConfig(level=logging.INFO, stream=sys.stderr)
                logger = logging.getLogger("ingestion_subprocess")

                config = json.loads(sys.stdin.read())
                logger.info("Subprocess started, %d file(s)", len(config["file_paths"]))

                from OpenDsStar.ingestion.docling_based_ingestion.docling_description_builder import (
                    DoclingDescriptionBuilder,
                )
                from lfx.base.data.docling_utils import _deserialize_pydantic_model

                llm = _deserialize_pydantic_model(config["llm_config"])
                logger.info("LLM deserialized: %s", type(llm).__name__)

                builder = DoclingDescriptionBuilder(
                    cache_dir=config["cache_dir"],
                    llm=llm,
                    embedding_model=config["embedding_model"],
                    batch_size=config["batch_size"],
                    enable_caching=True,
                )

                file_paths = [Path(p) for p in config["file_paths"]]
                logger.info("Calling describe_files with %d file(s)...", len(file_paths))
                analysis_results, _ = builder.describe_files(file_paths)
                logger.info("describe_files returned %d result(s)", len(analysis_results))

                output = []
                for doc_id, result in analysis_results.items():
                    success = result.get("success", False)
                    logger.info("  %s: success=%s file_path=%s", doc_id, success, result.get("file_path", ""))
                    if success:
                        output.append({
                            "text": result.get("answer", ""),
                            "file_path": result.get("file_path", ""),
                        })

                logger.info("Outputting %d successful description(s)", len(output))
                json.dump(output, sys.stdout)
            """)

            proc = subprocess.run(  # noqa: S603
                [sys.executable, "-c", script],
                check=False,
                input=json.dumps(config),
                capture_output=True,
                text=True,
                timeout=600,
            )

            _dbg(f"Subprocess finished, returncode={proc.returncode}")
            _dbg(f"Subprocess stdout length: {len(proc.stdout)}")
            _dbg(f"Subprocess stderr length: {len(proc.stderr)}")

            # Log subprocess stderr
            if proc.stderr:
                for line in proc.stderr.strip().split("\n"):
                    _dbg(f"[subprocess] {line}")

            if proc.returncode != 0:
                _dbg(f"SUBPROCESS FAILED with exit code {proc.returncode}")
                _dbg(f"stderr tail: {proc.stderr[-2000:] if proc.stderr else 'empty'}")
                err = proc.stderr[-2000:] if proc.stderr else "Unknown error"
                msg = f"Ingestion subprocess failed (exit code {proc.returncode}): {err}"
                raise RuntimeError(msg)

            _dbg(f"Subprocess stdout preview: {proc.stdout[:500]!r}")

            try:
                output = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                _dbg(f"JSON DECODE ERROR: {e}")
                _dbg(f"stdout was: {proc.stdout[:1000]!r}")
                msg = f"Invalid JSON from subprocess: {e}. stderr={proc.stderr[-500:]}"
                raise RuntimeError(msg) from e

            _dbg(f"Parsed {len(output)} results from subprocess")

            results: list[Data] = []
            for i, item in enumerate(output):
                _dbg(f"  result[{i}]: file_path={item.get('file_path', '')}, text_len={len(item.get('text', ''))}")
                results.append(
                    Data(
                        data={
                            "text": item["text"],
                            "file_path": item["file_path"],
                        },
                    )
                )

            _dbg(f"Returning {len(results)} Data object(s)")
            _dbg("========== generate_descriptions DONE ==========")
            return results  # noqa: TRY300

        except Exception as e:
            _dbg(f"EXCEPTION: {type(e).__name__}: {e}")
            _dbg(traceback.format_exc())
            raise
