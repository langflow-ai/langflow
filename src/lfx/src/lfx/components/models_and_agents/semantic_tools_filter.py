r"""Semantic Tools Filter component for Langflow.

## Motivation

Modern AI agents often have access to hundreds of tools from MCP servers, APIs, and custom
integrations. However, LLMs have limited context windows and struggle with tool selection
when presented with too many options. This leads to:

- **Token waste**: Sending 100+ tool descriptions consumes valuable context space
- **Poor tool selection**: LLMs get confused and pick wrong tools from large sets
- **Slower responses**: More tools = longer processing time
- **Higher costs**: Every tool description costs tokens on every request

This component solves these problems by intelligently filtering tools BEFORE they reach
the agent, ensuring only the most relevant tools are presented based on the user's query.

## What It Does

Filters tools from MCP servers (or any tool source) based on semantic similarity
to the user's query. Place between a tool source and an Agent to reduce the number
of tools the agent sees, saving context window tokens and improving tool selection.

Two independently toggleable stages:
  1. Embedding similarity pre-filter  →  top_k candidates  (fast & cheap)
     - Optional LLM description augmentation for richer embeddings
     - Automatic dependency detection: LLM identifies prerequisite tools during augmentation
     - Dependency-based expansion: adds related tools (e.g., location service for weather)
  2. LLM reranker                     →  top_p final tools  (precise)

Users can enable either stage, both, or neither (pass-through).

## Dependency Detection

When augmentation is enabled, the LLM analyzes each tool and identifies dependency keywords
(e.g., "weather" tool depends on "location", "geocoding"). These dependencies are cached
alongside descriptions. During filtering, if a tool is selected, any tools matching its
dependency keywords are automatically included, ensuring prerequisite tools are available.
This happens at zero runtime cost since dependencies are pre-computed and cached.

## Persistent Cache

All computed data (embeddings, augmented descriptions, and tool dependencies) is cached
in a platform-specific cache directory. The cache is keyed by a hash of the tool set,
so it automatically refreshes when tools change (added, removed, or modified).
This ensures expensive LLM and embedding operations only run once per unique tool set,
improving performance on subsequent runs.

Cache locations:
- Linux: ~/.cache/langflow/semantic_filter/cache.json
- macOS: ~/Library/Caches/langflow/semantic_filter/cache.json
- Windows: %LOCALAPPDATA%\\langflow\\langflow\\Cache\\semantic_filter\\cache.json
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import numpy as np

from lfx.custom import Component
from lfx.io import (
    BoolInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
)

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseLanguageModel
    from langchain_core.tools import BaseTool


class SemanticToolsFilterComponent(Component):
    display_name = "Semantic Tools Filter"
    description = (
        "Filters tools by semantic similarity to the user query. "
        "Connect between a tool source (e.g. MCP Tools) and an Agent "
        "to pass only the most relevant tools. "
        "Enable Embedding Filter, LLM Reranker, or both. "
        "When augmentation is enabled, automatically detects and includes prerequisite tools "
        "(e.g., adds location service when weather tool is selected)."
    )
    icon = "filter"
    name = "SemanticToolsFilter"
    beta = True

    _DEFAULT_AUGMENTATION_PROMPT = (
        "For each tool, provide:\n"
        "1. An extended description optimized for semantic search (2-3 sentences)\n"
        "2. A list of dependency tool types this tool commonly needs\n\n"
        "Include in description: what the tool does, typical use cases, example queries, "
        "and related concepts.\n\n"
        "Example format:\n"
        "Tool: get_weather\n"
        "Description: Retrieves current weather conditions and forecasts for any location...\n"
        'Dependencies: ["location_service", "geocoding", "coordinates"]\n\n'
        "Tool: send_email\n"
        "Description: Sends email messages to recipients...\n"
        'Dependencies: ["contact_lookup", "user_directory", "authentication"]'
    )

    inputs = [
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            info="Tools to filter (e.g. from an MCP Tools node).",
        ),
        MessageTextInput(
            name="user_query",
            display_name="User Query",
            info="The user question used to rank tools by relevance.",
        ),
        # --- Stage 1: Embedding pre-filter ---
        BoolInput(
            name="use_embeddings",
            display_name="Use Embedding Filter",
            value=True,
            real_time_refresh=True,
            info="Enable embedding-based similarity pre-filtering.",
        ),
        BoolInput(
            name="augment_descriptions",
            display_name="Augment Tool Descriptions",
            value=False,
            real_time_refresh=True,
            info=(
                "Use an LLM to generate enriched alternative descriptions "
                "for each tool. Both original and augmented descriptions are "
                "embedded; the best similarity score wins. "
                "Also detects tool dependencies (e.g., weather needs location) "
                "and automatically includes prerequisite tools in results."
            ),
        ),
        HandleInput(
            name="augmentation_model",
            display_name="Augmentation Model (LLM)",
            input_types=["LanguageModel"],
            required=False,
            info="LLM to generate extended tool descriptions. Required when augmentation is enabled.",
        ),
        IntInput(
            name="augmentation_samples",
            display_name="Augmentation Samples",
            value=1,
            info=(
                "Number of augmented description variants to generate per tool. "
                "Each variant is embedded independently; the best similarity "
                "score across all variants (plus the original) wins. "
                "Higher values improve recall at the cost of more LLM and "
                "embedding calls."
            ),
        ),
        MultilineInput(
            name="augmentation_prompt",
            display_name="Augmentation Prompt",
            value=_DEFAULT_AUGMENTATION_PROMPT,
            info=(
                "Instruction sent to the augmentation LLM. The tool list and "
                "JSON response format are appended automatically."
            ),
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            required=False,
            info="Embedding model for similarity pre-filter. Required when embedding filter is enabled.",
        ),
        IntInput(
            name="top_k",
            display_name="Top K (embedding pre-filter)",
            value=50,
            info="Number of candidate tools to keep after the embedding similarity stage.",
        ),
        FloatInput(
            name="similarity_threshold",
            display_name="Similarity Threshold",
            value=0.0,
            info="Minimum cosine similarity (0.0-1.0). Tools below this are excluded. 0.0 disables.",
            advanced=True,
        ),
        # --- Stage 2: LLM Reranker ---
        BoolInput(
            name="use_reranker",
            display_name="Use LLM Reranker",
            value=False,
            real_time_refresh=True,
            info="Enable LLM-based reranking of candidates.",
        ),
        HandleInput(
            name="reranker_model",
            display_name="Reranker Model (LLM)",
            input_types=["LanguageModel"],
            required=False,
            info="LLM for second-stage reranking. Required when reranker is enabled.",
        ),
        IntInput(
            name="top_p",
            display_name="Top P (final after rerank)",
            value=10,
            info="Number of tools to return after the LLM reranker. Only used when reranker is enabled.",
        ),
    ]

    outputs = [
        Output(
            display_name="Filtered Tools",
            name="filtered_tools",
            method="filter_tools",
            types=["Tool"],
        ),
    ]

    # ------------------------------------------------------------------
    # Dynamic field visibility
    # ------------------------------------------------------------------

    def update_build_config(
        self,
        build_config: dict,
        field_value: object,
        field_name: str,
    ) -> dict:
        """Show/hide fields based on toggle states."""
        # Apply the incoming change so we read consistent state
        if field_name in build_config:
            build_config[field_name]["value"] = field_value

        use_emb = build_config["use_embeddings"]["value"]
        augment = build_config["augment_descriptions"]["value"]
        use_rerank = build_config["use_reranker"]["value"]

        # Embedding section
        for name in ("embedding_model", "top_k", "similarity_threshold", "augment_descriptions"):
            build_config[name]["show"] = use_emb

        # Augmentation sub-section
        for name in ("augmentation_model", "augmentation_samples", "augmentation_prompt"):
            build_config[name]["show"] = use_emb and augment

        # Reranker section
        for name in ("reranker_model", "top_p"):
            build_config[name]["show"] = use_rerank

        return build_config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _logger():
        """Get a structlog logger (local import to survive exec)."""
        import structlog

        return structlog.get_logger("SemanticToolsFilter")

    # ------------------------------------------------------------------
    # Unified persistent cache
    #
    # A single JSON file in the platform-specific cache directory stores
    # all cached data:
    #   - embeddings  (numpy float32 arrays → serialised as lists of lists)
    #   - augmented tool descriptions (lists of strings)
    #   - tool dependencies (dict mapping tool names to dependency keywords)
    #
    # Augmented descriptions and dependencies are stored together in a
    # structured format:
    #   {"descriptions": [[...]], "dependencies": {"tool_name": ["keyword1", ...]}}
    #
    # Values that are numpy arrays are wrapped in a sentinel dict so they
    # can be round-tripped through JSON:
    #   {"__ndarray__": [[0.1, 0.2, ...], ...]}
    #
    # The in-memory dict lives on the ``sys`` module so it survives
    # Langflow re-exec'ing this source file between flow runs.
    # ------------------------------------------------------------------

    _CACHE_SYS_ATTR = "_semantic_tools_filter_cache"

    @classmethod
    def _get_cache_file_path(cls):
        """Get the platform-specific cache file path using platformdirs."""
        from pathlib import Path

        from platformdirs import user_cache_dir

        cache_dir = Path(user_cache_dir("langflow", "langflow")) / "semantic_filter"
        return cache_dir / "cache.json"

    @staticmethod
    def _encode_cache_value(value: object) -> object:
        """Prepare *value* for JSON serialisation.

        numpy arrays are wrapped in ``{"__ndarray__": <nested list>}`` so
        they can be distinguished from plain lists on deserialisation.
        """
        if isinstance(value, np.ndarray):
            return {"__ndarray__": value.tolist()}
        return value

    @staticmethod
    def _decode_cache_value(value: object) -> object:
        """Restore a value that was encoded by :meth:`_encode_cache_value`."""
        if isinstance(value, dict) and "__ndarray__" in value:
            return np.array(value["__ndarray__"], dtype=np.float32)
        return value

    @classmethod
    def _persistent_cache(cls) -> dict:
        """Return the unified in-memory cache, loading from disk on first access.

        The cache is stored as an attribute on the ``sys`` module so it
        survives Langflow re-exec'ing this file on every flow run.  On first
        access the cache is populated from the platform-specific cache directory.
        """
        import sys

        if not hasattr(sys, cls._CACHE_SYS_ATTR):
            cache: dict = {}
            cache_file = cls._get_cache_file_path()
            if cache_file.exists():
                try:
                    raw: dict = json.loads(cache_file.read_text())
                    cache = {k: cls._decode_cache_value(v) for k, v in raw.items()}
                except (ValueError, OSError):
                    pass
            setattr(sys, cls._CACHE_SYS_ATTR, cache)
        return getattr(sys, cls._CACHE_SYS_ATTR)

    @classmethod
    def _save_persistent_cache(cls) -> None:
        """Write the unified cache to disk in the platform-specific cache directory."""
        import sys

        cache = getattr(sys, cls._CACHE_SYS_ATTR, {})
        cache_file = cls._get_cache_file_path()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {k: cls._encode_cache_value(v) for k, v in cache.items()}
        cache_file.write_text(json.dumps(serialisable))

    # Keep old names as aliases so internal call-sites stay readable
    @classmethod
    def _cache(cls) -> dict:
        """Alias for :meth:`_persistent_cache` (embedding cache)."""
        return cls._persistent_cache()

    @classmethod
    def _augmentation_cache(cls) -> dict:
        """Alias for :meth:`_persistent_cache` (augmentation cache).

        Augmentation descriptions and embeddings share the same unified
        cache dict — keys are namespaced so they never collide.
        """
        return cls._persistent_cache()

    @classmethod
    def _persist_embedding_cache(cls) -> None:
        """Alias for :meth:`_save_persistent_cache`."""
        cls._save_persistent_cache()

    @classmethod
    def _persist_augmentation_cache(cls) -> None:
        """Alias for :meth:`_save_persistent_cache`."""
        cls._save_persistent_cache()

    @staticmethod
    def _tools_hash(tools: list[BaseTool]) -> str:
        """Deterministic hash over tool names + descriptions."""
        descriptors = sorted(f"{t.name}:{t.description}" for t in tools)
        joined = "|".join(descriptors)
        return hashlib.md5(joined.encode()).hexdigest()  # noqa: S324

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Cosine similarity between vector *a* (1-D) and matrix *b* (2-D)."""
        dot = b @ a
        norm_a = np.linalg.norm(a)
        norms_b = np.linalg.norm(b, axis=1)
        denom = norm_a * norms_b
        denom = np.where(denom == 0, 1e-10, denom)
        return dot / denom

    @staticmethod
    def _extract_json_array(text: str) -> str:
        """Extract the outermost JSON array from *text*, ignoring surrounding prose."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        start = text.find("[")
        if start == -1:
            msg = "No JSON array found in response"
            raise ValueError(msg)
        depth, end = 0, -1
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            msg = "Unbalanced brackets in response"
            raise ValueError(msg)
        return text[start:end]

    @staticmethod
    def _parse_partial_json_array(text: str) -> list | None:
        """Extract complete elements from a potentially truncated JSON array.

        Uses ``json.JSONDecoder.raw_decode()`` to parse elements one at a
        time, stopping at the first incomplete or corrupted element.  Useful
        when the LLM response was cut off before closing all brackets.

        Returns ``None`` if no complete elements could be recovered.
        """
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        start = text.find("[")
        if start == -1:
            return None

        decoder = json.JSONDecoder()
        results: list = []
        i = start + 1  # skip the opening '['

        while i < len(text):
            # Skip whitespace and commas
            while i < len(text) and text[i] in " \t\n\r,":
                i += 1
            if i >= len(text) or text[i] == "]":
                break
            try:
                obj, end_idx = decoder.raw_decode(text, i)
                results.append(obj)
                i = end_idx
            except json.JSONDecodeError:
                break  # Hit a truncated/invalid element

        return results if results else None

    @staticmethod
    def _parse_numbered_list(text: str) -> list[str] | None:
        """Try to parse a numbered-list response into a list of strings.

        Handles formats like::

            1. "description..."
            2. "description..."

        or::

            1) description...
            2) description...

        Returns ``None`` if the text doesn't look like a numbered list.
        """
        import re

        # Split on numbered markers at start of line: "1." or "1)"
        parts = re.split(r"(?:^|\n)\s*\d+[.)]\s*", text)
        # First part is preamble before "1.", skip it
        entries = []
        for p in parts[1:]:
            s = p.strip()
            # Strip surrounding double-quotes if present
            if len(s) >= 2 and s[0] == '"' and s[-1] == '"':  # noqa: PLR2004
                s = s[1:-1]
            if s:
                entries.append(s)
        return entries if entries else None

    def _get_tool_embeddings(
        self,
        tools: list[BaseTool],
        embedding_model: Embeddings,
        descriptions: list[str] | None = None,
    ) -> np.ndarray:
        """Return cached (or freshly computed) embeddings for the given tools.

        Parameters
        ----------
        descriptions:
            If provided, these strings are embedded instead of the default
            ``"name: description"`` texts.  Used for LLM-augmented descriptions.
        """
        import time

        logger = self._logger()
        cache = self._cache()

        if descriptions is None:
            descriptions = [f"{t.name}: {t.description}" for t in tools]
        else:
            # Prefix augmented descriptions with tool name for consistency
            descriptions = [f"{t.name}: {d}" for t, d in zip(tools, descriptions, strict=False)]

        # Cache key = model class + hash of exact content being embedded
        content_hash = hashlib.md5("|".join(descriptions).encode()).hexdigest()  # noqa: S324
        cache_key = f"{type(embedding_model).__name__}:{content_hash}"

        if cache_key in cache:
            logger.info(
                "Embedding cache HIT",
                component="SemanticToolsFilter",
                tool_count=len(tools),
                hash=content_hash[:8],
            )
            self.log(f"Cache HIT — reusing embeddings for {len(tools)} tools (hash={content_hash[:8]})")
            return cache[cache_key]

        start_time = time.perf_counter()
        logger.info(
            "Embedding cache MISS — computing",
            component="SemanticToolsFilter",
            tool_count=len(tools),
            hash=content_hash[:8],
        )
        for desc in descriptions:
            logger.debug("Embedding tool description", component="SemanticToolsFilter", description=desc)
        raw_embeddings = embedding_model.embed_documents(descriptions)
        embeddings = np.array(raw_embeddings, dtype=np.float32)

        elapsed = time.perf_counter() - start_time

        cache[cache_key] = embeddings
        self._persist_embedding_cache()

        logger.info(
            "Embedding computation complete",
            component="SemanticToolsFilter",
            tool_count=len(tools),
            elapsed_seconds=round(elapsed, 2),
        )
        self.log(f"Cache MISS — computed embeddings for {len(tools)} tools in {elapsed:.2f}s (hash={content_hash[:8]})")
        return embeddings

    # ------------------------------------------------------------------
    # LLM description augmentation
    # ------------------------------------------------------------------

    def _get_augmented_embeddings(
        self,
        tools: list[BaseTool],
        embedding_model: Embeddings,
        aug_model: BaseLanguageModel,
        instruction: str,
        num_samples: int = 1,
    ) -> tuple[np.ndarray, dict[str, list[str]]]:
        """Return augmented-description embeddings and dependencies, skipping the augmentation LLM entirely when cached.

        Returns:
            - np.ndarray: shape ``(N * num_samples, dim)`` where N = ``len(tools)``
            - dict[str, list[str]]: tool name -> dependency keywords

        Descriptions are ordered tool-major: all samples for tool 0, then
        all samples for tool 1, etc.  The caller can reshape to
        ``(N, num_samples, dim)`` to take per-tool max similarity.

        Cache key is predictable (tools hash + prompt hash + model names +
        num_samples) so we can check it *before* calling the augmentation LLM.
        """
        import time

        logger = self._logger()
        cache = self._cache()
        tools_hash = self._tools_hash(tools)
        prompt_hash = hashlib.md5(instruction.encode()).hexdigest()[:8]  # noqa: S324
        cache_key = (
            f"aug:{type(embedding_model).__name__}:{type(aug_model).__name__}:{tools_hash}:{prompt_hash}:s{num_samples}"
        )

        cached_value = cache.get(cache_key)
        if cached_value is not None:
            # New format: tuple of (embeddings, dependencies)
            if isinstance(cached_value, tuple) and len(cached_value) == 2:  # noqa: PLR2004
                embeddings, dependencies = cached_value
            else:
                # Backward compat: old cache entries are just embeddings
                embeddings = cached_value
                dependencies = {}

            logger.info(
                "Augmented embedding cache HIT — skipping augmentation LLM",
                component="SemanticToolsFilter",
                tool_count=len(tools),
                num_samples=num_samples,
                hash=tools_hash[:8],
            )
            self.log(f"Augmented embedding cache HIT for {len(tools)} tools — LLM not called")
            return embeddings, dependencies

        # Cache miss — need descriptions from augmentation LLM, then embed
        augmented, dependencies = self._augment_tool_descriptions(tools, aug_model, instruction, num_samples)

        # Flatten: tool-major order (all samples for tool 0, then tool 1, ...)
        descriptions = [f"{t.name}: {d}" for t, samples in zip(tools, augmented, strict=False) for d in samples]

        start_time = time.perf_counter()
        logger.info(
            "Computing augmented embeddings",
            component="SemanticToolsFilter",
            tool_count=len(tools),
            num_samples=num_samples,
            total_descriptions=len(descriptions),
            hash=tools_hash[:8],
        )
        for desc in descriptions:
            logger.debug("Embedding augmented description", component="SemanticToolsFilter", description=desc)
        raw = embedding_model.embed_documents(descriptions)
        embeddings = np.array(raw, dtype=np.float32)  # shape (N * num_samples, dim)

        elapsed = time.perf_counter() - start_time

        # Cache both embeddings and dependencies as a tuple
        cache[cache_key] = (embeddings, dependencies)
        self._persist_embedding_cache()

        logger.info(
            "Augmented embedding computation complete",
            component="SemanticToolsFilter",
            tool_count=len(tools),
            num_samples=num_samples,
            elapsed_seconds=round(elapsed, 2),
        )
        self.log(
            f"Computed & cached augmented embeddings for {len(tools)} tools in {elapsed:.2f}s "
            f"({num_samples} sample(s) each, {len(descriptions)} total, {len(dependencies)} with dependencies)"
        )
        return embeddings, dependencies

    def _augment_tool_descriptions(
        self,
        tools: list[BaseTool],
        llm: BaseLanguageModel,
        instruction: str,
        num_samples: int = 1,
    ) -> tuple[list[list[str]], dict[str, list[str]]]:
        """Use an LLM to generate enriched descriptions and dependencies for embedding.

        Returns:
            - list[list[str]]: *num_samples* augmented description strings per tool
            - dict[str, list[str]]: tool name -> list of dependency keywords

        Both are cached by tool-set hash + model class + prompt hash + sample count.
        """
        logger = self._logger()
        cache = self._augmentation_cache()
        tools_hash = self._tools_hash(tools)
        prompt_hash = hashlib.md5(instruction.encode()).hexdigest()[:8]  # noqa: S324
        cache_key = f"{type(llm).__name__}:{tools_hash}:{prompt_hash}:s{num_samples}"

        cached = cache.get(cache_key)
        if cached is not None:
            # New format: {"descriptions": [[...]], "dependencies": {...}}
            if isinstance(cached, dict) and "descriptions" in cached:
                descriptions = cached["descriptions"]
                dependencies = cached.get("dependencies", {})
            else:
                # Backward compat: old cache entries are list[str] or list[list[str]]
                descriptions = [[d] for d in cached] if cached and isinstance(cached[0], str) else cached
                dependencies = {}

            logger.info(
                "Augmentation cache HIT",
                component="SemanticToolsFilter",
                tool_count=len(tools),
                hash=tools_hash[:8],
            )
            self.log(f"Augmentation cache HIT — reusing descriptions for {len(tools)} tools")
            return descriptions, dependencies

        logger.info(
            "Augmentation cache MISS — generating",
            component="SemanticToolsFilter",
            tool_count=len(tools),
            model=type(llm).__name__,
            num_samples=num_samples,
        )

        tool_list_text = "\n".join(
            f"  #{i + 1}. {t.name}: {t.description or '(no description)'}" for i, t in enumerate(tools)
        )

        if num_samples == 1:
            format_instruction = (
                f"IMPORTANT: Respond with ONLY a valid JSON object with this structure:\n"
                f'{{"descriptions": [...], "dependencies": [...]}}\n\n'
                f'"descriptions" must be an array of exactly {len(tools)} strings '
                f"(one per tool, same order).\n"
                f'"dependencies" must be an array of exactly {len(tools)} arrays '
                f"of dependency keywords.\n\n"
                f'Example: {{"descriptions": ["desc1", "desc2"], '
                f'"dependencies": [["keyword1", "keyword2"], ["keyword3"]]}}'
            )
        else:
            format_instruction = (
                f"IMPORTANT: For each tool, generate exactly {num_samples} different "
                f"description variants, each emphasizing different aspects, use cases, "
                f"or phrasings to maximize recall during semantic search.\n\n"
                f"Respond with ONLY a valid JSON object with this structure:\n"
                f'{{"descriptions": [...], "dependencies": [...]}}\n\n'
                f'"descriptions" must be an array of exactly {len(tools)} sub-arrays, '
                f"each containing exactly {num_samples} strings.\n"
                f'"dependencies" must be an array of exactly {len(tools)} arrays of dependency keywords.\n\n'
                f"Example for 2 tools with {num_samples} variants:\n"
                f'{{"descriptions": [["var1", "var2"], ["var1", "var2"]], '
                f'"dependencies": [["dep1", "dep2"], ["dep3"]]}}'
            )

        prompt = (
            f"{instruction}\n\n"
            f"There are exactly {len(tools)} tools (some may share a name — "
            f"treat each numbered entry as a SEPARATE tool):\n{tool_list_text}\n\n"
            f"{format_instruction}"
        )

        logger.debug(
            "Augmentation prompt",
            component="SemanticToolsFilter",
            prompt=prompt,
        )

        response = llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)

        logger.info(
            "Augmentation LLM response",
            component="SemanticToolsFilter",
            raw_length=len(raw_text),
        )

        # Parse the response - try structured format first, fall back to old format
        dependencies: dict[str, list[str]] = {}
        try:
            # Try to extract JSON object (new format with dependencies)
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = raw_text[json_start:json_end]
                parsed_obj = json.loads(json_text)

                if isinstance(parsed_obj, dict) and "descriptions" in parsed_obj:
                    # New structured format
                    parsed = parsed_obj["descriptions"]
                    raw_deps = parsed_obj.get("dependencies", [])

                    # Build dependencies dict: tool_name -> [keywords]
                    for _i, (tool, deps) in enumerate(zip(tools, raw_deps, strict=False)):
                        if isinstance(deps, list):
                            dependencies[tool.name] = [str(d).lower() for d in deps if d]

                    logger.info(
                        "Parsed structured response with dependencies",
                        component="SemanticToolsFilter",
                        tools_with_deps=len(dependencies),
                    )
                else:
                    # Old format - just array
                    parsed = self._extract_json_array(raw_text)
                    parsed = json.loads(parsed)
            else:
                # No JSON object found, try array
                parsed = json.loads(self._extract_json_array(raw_text))

            if not isinstance(parsed, list):
                msg = "Response is not a list"
                raise TypeError(msg)

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            # Fallback: LLMs sometimes return numbered lists instead of JSON
            numbered = self._parse_numbered_list(raw_text)
            if numbered:
                logger.info(
                    "JSON parse failed — fell back to numbered-list parser",
                    component="SemanticToolsFilter",
                    error=str(exc),
                    parsed_count=len(numbered),
                )
                parsed = numbered
            else:
                logger.warning(
                    "Failed to parse augmented descriptions — falling back to originals",
                    component="SemanticToolsFilter",
                    error=str(exc),
                    raw=raw_text[:200],
                )
                self.log("Augmentation failed to parse — using original descriptions")
                return [[t.description or ""] * num_samples for t in tools], {}

        # Normalize into list[list[str]]
        if num_samples == 1:
            # LLM was asked for flat array of strings
            descriptions = [[d] if isinstance(d, str) else d for d in parsed]
        else:
            # LLM was asked for nested array of sub-arrays
            descriptions = []
            for entry in parsed:
                if isinstance(entry, str):
                    # LLM flattened — treat as single variant
                    descriptions.append([entry])
                elif isinstance(entry, list):
                    descriptions.append([str(s) for s in entry])
                else:
                    descriptions.append([str(entry)])

        # Lenient tool-count handling — pad with originals or truncate
        if len(descriptions) < len(tools):
            logger.warning(
                "LLM returned fewer tool entries than expected — padding with originals",
                component="SemanticToolsFilter",
                expected=len(tools),
                got=len(descriptions),
            )
            for t in tools[len(descriptions) :]:
                descriptions.append([t.description or ""] * num_samples)
        elif len(descriptions) > len(tools):
            logger.warning(
                "LLM returned more tool entries than expected — truncating",
                component="SemanticToolsFilter",
                expected=len(tools),
                got=len(descriptions),
            )
            descriptions = descriptions[: len(tools)]

        # Lenient per-tool sample count — pad or truncate each sub-list
        for i, (t, samples) in enumerate(zip(tools, descriptions, strict=False)):
            if len(samples) < num_samples:
                samples.extend([t.description or ""] * (num_samples - len(samples)))
                descriptions[i] = samples
            elif len(samples) > num_samples:
                descriptions[i] = samples[:num_samples]

        # Cache both descriptions and dependencies in new structured format
        cache[cache_key] = {
            "descriptions": descriptions,
            "dependencies": dependencies,
        }
        self._persist_augmentation_cache()

        dep_count = len(dependencies)
        self.log(
            f"Generated {num_samples} augmented description(s) per tool for {len(tools)} tools "
            f"({dep_count} with dependencies)"
        )

        for t, samples in zip(tools, descriptions, strict=False):
            for j, desc in enumerate(samples):
                logger.debug(
                    "Augmented description",
                    component="SemanticToolsFilter",
                    tool=t.name,
                    sample=j + 1,
                    description=desc[:120],
                )

            # Log dependencies if present
            if t.name in dependencies:
                logger.debug(
                    "Tool dependencies",
                    component="SemanticToolsFilter",
                    tool=t.name,
                    dependencies=dependencies[t.name],
                )

        return descriptions, dependencies

    # ------------------------------------------------------------------
    # Dependency-based expansion
    # ------------------------------------------------------------------

    def _expand_with_dependencies(
        self,
        candidates: list[tuple[BaseTool, float]],
        all_tools: list[BaseTool],
        tool_dependencies: dict[str, list[str]],
        scored_all: list[tuple[BaseTool, float]],
        logger,
    ) -> list[tuple[BaseTool, float]]:
        """Expand candidate set by including tools that match dependency keywords.

        For each selected candidate tool, check if any other tools match its
        dependency keywords. Add matching tools to candidates if not already present.

        Args:
            candidates: Current top-k candidates
            all_tools: All available tools
            tool_dependencies: Dict mapping tool names to dependency keywords
            scored_all: All tools with their similarity scores
            logger: Logger instance

        Returns:
            Expanded list of candidates (may be larger than original)
        """
        candidate_names = {t.name for t, _ in candidates}
        added_tools: list[tuple[BaseTool, float]] = []

        # Build a map of tool name -> (tool, score) for quick lookup
        tool_score_map = {t.name: (t, s) for t, s in scored_all}

        # For each candidate, check if any other tools match its dependencies
        for candidate_tool, _ in candidates:
            deps = tool_dependencies.get(candidate_tool.name, [])
            if not deps:
                continue

            # Check all other tools for dependency matches
            for other_tool in all_tools:
                if other_tool.name in candidate_names:
                    continue  # Already a candidate

                # Check if tool name or description contains any dependency keyword
                tool_text = f"{other_tool.name} {other_tool.description or ''}".lower()

                for dep_keyword in deps:
                    if dep_keyword in tool_text:
                        # Found a dependency match - add this tool
                        if other_tool.name in tool_score_map:
                            tool_score_pair = tool_score_map[other_tool.name]
                            added_tools.append(tool_score_pair)
                            candidate_names.add(other_tool.name)

                            logger.info(
                                "Added dependency tool",
                                component="SemanticToolsFilter",
                                required_by=candidate_tool.name,
                                dependency_keyword=dep_keyword,
                                added_tool=other_tool.name,
                            )
                        break  # Only add once per tool

        if added_tools:
            logger.info(
                "Dependency expansion complete",
                component="SemanticToolsFilter",
                original_count=len(candidates),
                added_count=len(added_tools),
                final_count=len(candidates) + len(added_tools),
            )
            self.log(
                f"Dependency expansion: added {len(added_tools)} tools based on dependencies "
                f"({len(candidates)} → {len(candidates) + len(added_tools)})"
            )
            return candidates + added_tools

        return candidates

    # ------------------------------------------------------------------
    # LLM reranker
    # ------------------------------------------------------------------

    def _rerank_with_llm(
        self,
        query: str,
        candidates: list[tuple[BaseTool, float]],
        llm: BaseLanguageModel,
        top_p: int,
    ) -> list[tuple[BaseTool, float]]:
        """Use an LLM to pick the best *top_p* tools from the candidates."""
        logger = self._logger()

        tool_list_text = "\n".join(f"{i + 1}. {t.name} — {t.description}" for i, (t, _) in enumerate(candidates))

        prompt = (
            f"You are a tool-selection assistant. The user's query is:\n"
            f'"{query}"\n\n'
            f"Available tools:\n{tool_list_text}\n\n"
            f"Select up to {top_p} most relevant tools for this query. "
            f"Return multiple tools if they could work together or provide complementary functionality. "
            f"Only return fewer than {top_p} if there are genuinely no other relevant tools.\n\n"
            f"Respond ONLY with a JSON array of the selected tool numbers "
            f"(1-indexed), e.g. [1, 3, 5]. No explanation."
        )

        logger.info(
            "LLM reranker invoked",
            component="SemanticToolsFilter",
            candidate_count=len(candidates),
            top_p=top_p,
            query=query[:80],
        )

        response = llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)

        logger.debug(
            "LLM reranker response",
            component="SemanticToolsFilter",
            raw=raw_text.strip(),
        )

        # Parse the JSON array from the response
        try:
            selected_indices = json.loads(self._extract_json_array(raw_text))
            if not isinstance(selected_indices, list):
                selected_indices = [selected_indices]
            indices = [i - 1 for i in selected_indices if isinstance(i, int) and 1 <= i <= len(candidates)]
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "LLM reranker returned unparseable response — falling back to embedding ranking",
                component="SemanticToolsFilter",
                raw=raw_text.strip(),
            )
            return candidates[:top_p]

        if not indices:
            logger.warning(
                "LLM reranker selected no valid tools — falling back to embedding ranking",
                component="SemanticToolsFilter",
            )
            return candidates[:top_p]

        reranked = [candidates[i] for i in indices[:top_p]]

        logger.info(
            "LLM reranker selection",
            component="SemanticToolsFilter",
            selected=[{"rank": r, "tool": t.name} for r, (t, _) in enumerate(reranked, 1)],
        )
        return reranked

    # ------------------------------------------------------------------
    # Main output method
    # ------------------------------------------------------------------

    def filter_tools(self) -> list:
        """Filter tools through independently toggleable stages."""
        import time

        logger = self._logger()

        tools: list[BaseTool] = self.tools
        query: str = self.user_query
        use_embeddings: bool = self.use_embeddings
        use_reranker: bool = self.use_reranker

        logger.info(
            "filter_tools called",
            component="SemanticToolsFilter",
            use_embeddings=use_embeddings,
            use_reranker=use_reranker,
            tools_in=len(tools) if tools else 0,
        )
        # Query may contain sensitive business data - only log in debug mode for troubleshooting
        logger.debug(
            "filter_tools query",
            component="SemanticToolsFilter",
            query=query[:120],
        )

        # Edge case: no tools
        if not tools:
            logger.warning("No tools provided", component="SemanticToolsFilter")
            self.status = "No tools provided — returning empty list."
            return []

        logger.info(
            "Incoming tools",
            component="SemanticToolsFilter",
            count=len(tools),
        )
        logger.debug(
            "Incoming tool names",
            component="SemanticToolsFilter",
            tools=[t.name for t in tools],
        )

        # Neither stage enabled — pass-through
        if not use_embeddings and not use_reranker:
            logger.info(
                "Both stages disabled — returning all tools",
                component="SemanticToolsFilter",
                count=len(tools),
            )
            tool_names = [t.name for t in tools]
            self.status = f"No filtering enabled — returning all {len(tools)} tools: {', '.join(tool_names)}"
            return tools

        stages_used: list[str] = []
        # scored_all tracks (tool, similarity_score) — score is 0.0 when embeddings are skipped
        scored_all: list[tuple[BaseTool, float]] = [(t, 0.0) for t in tools]

        # ----------------------------------------------------------
        # Stage 1: Embedding similarity pre-filter
        # ----------------------------------------------------------
        if use_embeddings:
            stage1_start = time.perf_counter()

            embedding_model: Embeddings = self.embedding_model
            top_k: int = self.top_k
            threshold: float = self.similarity_threshold

            if embedding_model is None:
                msg = "Embedding Model must be connected when the embedding filter is enabled."
                raise ValueError(msg)

            # Always embed original descriptions
            tool_embeddings = self._get_tool_embeddings(tools, embedding_model)

            query_embedding = np.array(
                embedding_model.embed_query(query),
                dtype=np.float32,
            )

            similarities = self._cosine_similarity(query_embedding, tool_embeddings)

            # Optionally embed augmented descriptions as alternatives
            tool_dependencies: dict[str, list[str]] = {}
            if self.augment_descriptions:
                aug_model = getattr(self, "augmentation_model", None)
                if aug_model is None:
                    msg = "Augmentation Model must be connected when description augmentation is enabled."
                    raise ValueError(msg)
                num_samples: int = self.augmentation_samples
                aug_embeddings, tool_dependencies = self._get_augmented_embeddings(
                    tools,
                    embedding_model,
                    aug_model,
                    self.augmentation_prompt,
                    num_samples,
                )
                # aug_embeddings shape: (N * num_samples, dim)
                aug_similarities = self._cosine_similarity(query_embedding, aug_embeddings)
                # Reshape to (N, num_samples) and take per-tool max across all variants
                aug_similarities = aug_similarities.reshape(len(tools), num_samples).max(axis=1)
                # Per-tool max: a tool matches if *any* description (original or augmented) is close
                similarities = np.maximum(similarities, aug_similarities)

                logger.info(
                    "Loaded tool dependencies",
                    component="SemanticToolsFilter",
                    tools_with_deps=len(tool_dependencies),
                )

            scored_all = sorted(
                zip(tools, similarities.tolist(), strict=False),
                key=lambda x: x[1],
                reverse=True,
            )

            # Log only top_k ranking (tool names and scores only)
            ranking = [
                {"rank": r, "tool": t.name, "score": round(s, 4)} for r, (t, s) in enumerate(scored_all[:top_k], 1)
            ]
            logger.debug(
                "Embedding similarity ranking",
                component="SemanticToolsFilter",
                query=query[:80],
                ranking=ranking,
            )

            # Apply threshold
            if threshold > 0:
                before_count = len(scored_all)
                scored_all = [(t, s) for t, s in scored_all if s >= threshold]
                dropped = before_count - len(scored_all)
                if dropped:
                    logger.info(
                        "Threshold filter applied",
                        component="SemanticToolsFilter",
                        threshold=threshold,
                        dropped=dropped,
                    )

            # Take top_k candidates
            candidates = scored_all[:top_k]

            # Expand candidates based on dependencies (if available)
            if tool_dependencies:
                candidates = self._expand_with_dependencies(candidates, tools, tool_dependencies, scored_all, logger)

            stage1_elapsed = time.perf_counter() - stage1_start

            logger.debug(
                "Stage 1 (embedding) complete",
                component="SemanticToolsFilter",
                candidates=[t.name for t, _ in candidates],
                candidate_count=len(candidates),
                elapsed_seconds=round(stage1_elapsed, 2),
            )
            self.log(f"Stage 1 (embedding filter) completed in {stage1_elapsed:.2f}s — {len(candidates)} candidates")
            stages_used.append("embedding" + ("+augmented" if self.augment_descriptions else ""))
        else:
            # Embeddings disabled — all tools pass to next stage (or output)
            candidates = scored_all
            logger.info(
                "Embedding stage skipped — all tools forwarded",
                component="SemanticToolsFilter",
                count=len(candidates),
            )

        # ----------------------------------------------------------
        # Stage 2: LLM reranker
        # ----------------------------------------------------------
        if use_reranker and candidates:
            stage2_start = time.perf_counter()

            reranker: BaseLanguageModel | None = getattr(self, "reranker_model", None)
            top_p: int = self.top_p

            if reranker is None:
                msg = "Reranker Model must be connected when the LLM reranker is enabled."
                raise ValueError(msg)

            selected = self._rerank_with_llm(query, candidates, reranker, top_p)

            stage2_elapsed = time.perf_counter() - stage2_start
            logger.info(
                "Stage 2 (LLM reranker) complete",
                component="SemanticToolsFilter",
                selected_count=len(selected),
                elapsed_seconds=round(stage2_elapsed, 2),
            )
            self.log(f"Stage 2 (LLM reranker) completed in {stage2_elapsed:.2f}s — {len(selected)} tools selected")
            stages_used.append("reranker")
        else:
            selected = candidates

        stage_label = " → ".join(stages_used) if stages_used else "pass-through"
        selected_names = [t.name for t, _ in selected]
        all_candidate_names = [t.name for t, _ in candidates]
        rejected_names = [n for n in all_candidate_names if n not in selected_names]

        logger.debug(
            "Tool selection complete",
            component="SemanticToolsFilter",
            stage=stage_label,
            selected=selected_names,
            selected_count=len(selected),
            rejected=rejected_names,
            rejected_count=len(rejected_names),
            total=len(tools),
        )

        logger.info(
            "Tool filtering complete",
            component="SemanticToolsFilter",
            stage=stage_label,
            selected_count=len(selected),
            rejected_count=len(rejected_names),
            total=len(tools),
        )

        # Build status summary (visible in the Langflow node UI)
        top_k_val = self.top_k if use_embeddings else "-"
        top_p_val = self.top_p if use_reranker else "-"
        threshold_val = self.similarity_threshold if use_embeddings else "-"

        status_lines = [
            f'Query: "{query[:100]}"',
            f"Pipeline: {stage_label}",
            f"Selected {len(selected)}/{len(tools)} tools "
            f"(top_k={top_k_val}, top_p={top_p_val}, threshold={threshold_val}):",
            "",
        ]
        for tool, score in selected:
            score_str = f"sim={score:.4f}" if use_embeddings else "n/a"
            status_lines.append(f"  + {tool.name} ({score_str})")

        # Rejected tools
        rejected_from_candidates = [(t, s) for t, s in candidates if t.name not in selected_names]
        rejected_from_rest = [(t, s) for t, s in scored_all[self.top_k :]] if use_embeddings else []
        if rejected_from_candidates or rejected_from_rest:
            status_lines.append("")
            status_lines.append("Rejected:")
            for tool, score in rejected_from_candidates:
                reason = "reranker dropped" if use_reranker else "below top_k"
                score_str = f"sim={score:.4f}" if use_embeddings else "n/a"
                status_lines.append(f"  - {tool.name} ({score_str}) [{reason}]")
            for tool, score in rejected_from_rest:
                status_lines.append(f"  - {tool.name} (sim={score:.4f}) [below top_k]")
        self.status = "\n".join(status_lines)

        return [t for t, _s in selected]
