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


_DEFAULT_TIMEOUT_SECONDS = 3600


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
            name="timeout",
            display_name="Timeout (seconds)",
            value=_DEFAULT_TIMEOUT_SECONDS,
            info="Maximum time in seconds for the ingestion subprocess. Increase for large file sets.",
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

    def _extract_file_paths(self) -> list[str]:
        """Extract file paths from self.file_data inputs."""
        from lfx.schema.dataframe import DataFrame

        file_paths: list[str] = []
        for i, item in enumerate(self.file_data):
            _dbg(f"  item[{i}] type: {type(item).__name__}")
            if isinstance(item, DataFrame):
                fp = item.attrs.get("source_file_path", "")
                if fp:
                    _dbg(f"  item[{i}] DataFrame source_file_path from attrs={fp!r}")
                    file_paths.append(str(Path(fp)))
                elif "file_path" in item.columns and not item.empty:
                    unique_paths = item["file_path"].dropna().unique().tolist()
                    _dbg(f"  item[{i}] DataFrame found {len(unique_paths)} file_path(s) in column")
                    file_paths.extend(str(Path(path)) for path in unique_paths if path)
                else:
                    _dbg(
                        f"  WARNING: item[{i}] DataFrame has no source_file_path in attrs or file_path column, skipping"
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
        return file_paths

    def generate_descriptions(self) -> list[Data]:
        _dbg("========== generate_descriptions CALLED ==========")

        try:
            _dbg(f"self.file_data type: {type(self.file_data).__name__}")
            _dbg(f"self.file_data length: {len(self.file_data)}")

            file_paths = self._extract_file_paths()
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
                total = len(file_paths)
                logger.info("Calling describe_files with %d file(s)...", total)
                sys.stderr.flush()
                analysis_results, _ = builder.describe_files(file_paths)
                logger.info("describe_files returned %d result(s)", len(analysis_results))
                sys.stderr.flush()

                output = []
                failed = []
                for doc_id, result in analysis_results.items():
                    success = result.get("success", False)
                    fp = result.get("file_path", doc_id)
                    logger.info("  %s: success=%s file_path=%s", doc_id, success, fp)
                    if success:
                        output.append({
                            "text": result.get("answer", ""),
                            "file_path": fp,
                        })
                    else:
                        error = result.get("error", "Unknown error")
                        failed.append({"file_path": fp, "error": str(error)})

                logger.info("Outputting %d successful, %d failed description(s)", len(output), len(failed))
                json.dump({"results": output, "failed": failed, "total": total}, sys.stdout)
            """)

            timeout_seconds = getattr(self, "timeout", _DEFAULT_TIMEOUT_SECONDS) or _DEFAULT_TIMEOUT_SECONDS

            proc = subprocess.Popen(  # noqa: S603
                [sys.executable, "-u", "-c", script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Send config to stdin and close it so the subprocess can proceed
            proc.stdin.write(json.dumps(config))
            proc.stdin.close()

            # Stream stderr in real-time while draining stdout to avoid pipe deadlock.
            # We must read both pipes concurrently — if stdout fills up (64KB default)
            # while we only read stderr, the subprocess blocks on stdout.write().
            import select
            import time

            stderr_lines: list[str] = []
            stdout_chunks: list[str] = []
            start_time = time.monotonic()
            stderr_buf = ""

            # Check if select() is usable (not available with StringIO in tests)
            try:
                proc.stderr.fileno()
                use_select = True
            except Exception:  # noqa: BLE001
                use_select = False

            while proc.poll() is None:
                elapsed = time.monotonic() - start_time
                if elapsed > timeout_seconds:
                    proc.kill()
                    proc.wait()
                    msg = (
                        f"Ingestion subprocess timed out after {timeout_seconds}s. "
                        f"Increase the Timeout setting for large file sets."
                    )
                    raise TimeoutError(msg)

                if use_select:
                    ready, _, _ = select.select([proc.stderr, proc.stdout], [], [], 1.0)
                    for stream in ready:
                        chunk = stream.read(4096)
                        if not chunk:
                            continue
                        if stream is proc.stderr:
                            stderr_buf += chunk
                            while "\n" in stderr_buf:
                                line, stderr_buf = stderr_buf.split("\n", 1)
                                line = line.strip()
                                if line:
                                    _dbg(f"[subprocess] {line}")
                                    self.log(line)
                                    stderr_lines.append(line)
                        else:
                            stdout_chunks.append(chunk)
                else:
                    # Drain pipes to prevent deadlock when select() is unavailable.
                    # Without draining, the subprocess can block if stdout/stderr
                    # exceed the 64KB pipe buffer.
                    chunk = proc.stdout.read(4096)
                    if chunk:
                        stdout_chunks.append(chunk)
                    chunk = proc.stderr.read(4096)
                    if chunk:
                        stderr_buf += chunk
                        while "\n" in stderr_buf:
                            line, stderr_buf = stderr_buf.split("\n", 1)
                            line = line.strip()
                            if line:
                                _dbg(f"[subprocess] {line}")
                                self.log(line)
                                stderr_lines.append(line)
                    time.sleep(0.1)

            # Read any remaining data after process exits
            remaining_stderr = proc.stderr.read()
            if remaining_stderr:
                stderr_buf += remaining_stderr
            for remaining_line in stderr_buf.strip().split("\n"):
                stripped = remaining_line.strip()
                if stripped:
                    _dbg(f"[subprocess] {stripped}")
                    self.log(stripped)
                    stderr_lines.append(stripped)

            remaining_stdout = proc.stdout.read()
            if remaining_stdout:
                stdout_chunks.append(remaining_stdout)
            stdout_data = "".join(stdout_chunks)

            _dbg(f"Subprocess finished, returncode={proc.returncode}")
            _dbg(f"Subprocess stdout length: {len(stdout_data)}")

            if proc.returncode != 0:
                _dbg(f"SUBPROCESS FAILED with exit code {proc.returncode}")
                stderr_tail = "\n".join(stderr_lines[-20:])
                msg = f"Ingestion subprocess failed (exit code {proc.returncode}): {stderr_tail}"
                raise RuntimeError(msg)

            _dbg(f"Subprocess stdout preview: {stdout_data[:500]!r}")

            try:
                output = json.loads(stdout_data)
            except json.JSONDecodeError as e:
                _dbg(f"JSON DECODE ERROR: {e}")
                _dbg(f"stdout was: {stdout_data[:1000]!r}")
                stderr_tail = "\n".join(stderr_lines[-10:])
                msg = f"Invalid JSON from subprocess: {e}. stderr={stderr_tail}"
                raise RuntimeError(msg) from e

            # Parse structured output: {results: [...], failed: [...], total: N}
            successful = output.get("results", [])
            failed = output.get("failed", [])
            total = output.get("total", len(file_paths))

            _dbg(f"Parsed {len(successful)} successful, {len(failed)} failed out of {total}")

            # Fail if any descriptions were not generated
            if failed:
                # Group failures by error reason
                errors_by_reason: dict[str, list[str]] = {}
                for f in failed:
                    if isinstance(f, dict):
                        reason = f.get("error", "Unknown error")
                        name = Path(f.get("file_path", "?")).name
                    else:
                        reason = "Unknown error"
                        name = Path(f).name
                    errors_by_reason.setdefault(reason, []).append(name)

                # Build a clear error message
                parts = [f"Ingestion failed: {len(failed)}/{total} files did not get descriptions."]
                max_sample = 5
                for reason, files in errors_by_reason.items():
                    sample = files[:max_sample]
                    extra = f" (and {len(files) - max_sample} more)" if len(files) > max_sample else ""
                    parts.append(f"  - {reason}: {sample}{extra}")

                msg = "\n".join(parts)
                self.log(msg)
                raise RuntimeError(msg)

            results: list[Data] = []
            for i, item in enumerate(successful):
                _dbg(f"  result[{i}]: file_path={item.get('file_path', '')}, text_len={len(item.get('text', ''))}")
                results.append(
                    Data(
                        data={
                            "text": item["text"],
                            "file_path": item["file_path"],
                        },
                    )
                )

            # Log all descriptions
            for r in results:
                fp = r.data.get("file_path", "")
                desc = r.data.get("text", "")
                self.log(f"Created description: file: {fp}\ndescription:\n{desc}")

            if not results:
                msg = f"Ingestion produced 0 descriptions for {total} files. Check LLM configuration."
                raise RuntimeError(msg)

            _dbg(f"Returning {len(results)} Data object(s)")
            _dbg("========== generate_descriptions DONE ==========")
            return results  # noqa: TRY300

        except Exception as e:
            _dbg(f"EXCEPTION: {type(e).__name__}: {e}")
            _dbg(traceback.format_exc())
            raise
