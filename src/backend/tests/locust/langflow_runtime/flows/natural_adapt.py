"""Natural fixture adaptation: pin starter topologies; stub only vendor edges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.locust.langflow_runtime.flows.defaults import (
    DEFAULT_KB_NAME,
    DEFAULT_OUTBOUND_API_KEY_VAR,
    DEFAULT_OUTBOUND_MODEL,
    DEFAULT_OUTBOUND_PROVIDER,
    REPO_ROOT,
)

STARTERS_DIR = REPO_ROOT / "src" / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"

SHAPE_STARTERS: dict[str, str] = {
    "basic_prompting": "Basic Prompting.json",
    "simple_agent": "Simple Agent.json",
    "memory_chatbot": "Memory Chatbot.json",
    "vector_store_rag": "Vector Store RAG.json",
    "file_parser_agent": "Financial Report Parser.json",
}

# Node types that must appear in both stubbed and live fixtures for each shape.
NATURAL_TOPOLOGY: dict[str, frozenset[str]] = {
    "basic_prompting": frozenset({"ChatInput", "ChatOutput", "Prompt", "LanguageModelComponent"}),
    "simple_agent": frozenset({"ChatInput", "ChatOutput", "Agent", "URLComponent", "UnifiedWebSearch"}),
    "memory_chatbot": frozenset({"ChatInput", "ChatOutput", "Agent", "MemoryBase"}),
    "vector_store_rag": frozenset({"ChatInput", "ChatOutput", "Agent", "Knowledge", "Prompt"}),
    "file_parser_agent": frozenset({"ChatOutput", "Agent", "File", "ParserComponent"}),
}

_COMPONENTS = Path(__file__).resolve().parents[1] / "components"


def _read_component_source(filename: str) -> str:
    return (_COMPONENTS / filename).read_text(encoding="utf-8")


def node_types(payload: dict[str, Any]) -> set[str]:
    types: set[str] = set()
    for node in payload.get("data", {}).get("nodes", []):
        ntype = node.get("data", {}).get("type")
        if ntype and ntype not in {"note", "noteNode"}:
            types.add(str(ntype))
    return types


def assert_topology(shape: str, payload: dict[str, Any]) -> None:
    required = NATURAL_TOPOLOGY[shape]
    present = node_types(payload)
    missing = sorted(required - present)
    if missing:
        msg = f"natural {shape}: missing required node types {missing}; present={sorted(present)}"
        raise AssertionError(msg)


def _iter_nodes(payload: dict[str, Any]):
    yield from payload.get("data", {}).get("nodes", [])


def _replace_code_for_types(payload: dict[str, Any], type_names: set[str], source: str) -> None:
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") not in type_names:
            continue
        template = (data.get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict):
            code["value"] = source


def _drop_note_nodes(payload: dict[str, Any]) -> None:
    nodes = payload.get("data", {}).get("nodes") or []
    keep_ids = set()
    for n in nodes:
        ntype = (n.get("data") or {}).get("type")
        if not ntype or ntype in {"note", "noteNode"}:
            continue
        keep_ids.add(n["id"])
    payload["data"]["nodes"] = [n for n in nodes if n["id"] in keep_ids]
    edges = payload.get("data", {}).get("edges") or []
    payload["data"]["edges"] = [e for e in edges if e.get("source") in keep_ids and e.get("target") in keep_ids]


def _set_chat_store_flags(payload: dict[str, Any], *, store: bool) -> None:
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") not in {"ChatInput", "ChatOutput"}:
            continue
        template = (data.get("node") or {}).get("template") or {}
        field = template.get("should_store_message")
        if isinstance(field, dict):
            field["value"] = store


def _bind_live_llm(payload: dict[str, Any]) -> None:
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") not in {"LanguageModelComponent", "Agent"}:
            continue
        template = (data.get("node") or {}).get("template") or {}
        if "model" in template and isinstance(template["model"], dict):
            template["model"]["value"] = [{"name": DEFAULT_OUTBOUND_MODEL, "provider": DEFAULT_OUTBOUND_PROVIDER}]
        if "api_key" in template and isinstance(template["api_key"], dict):
            template["api_key"]["value"] = DEFAULT_OUTBOUND_API_KEY_VAR
            template["api_key"]["load_from_db"] = True
        if "provider" in template and isinstance(template["provider"], dict):
            template["provider"]["value"] = DEFAULT_OUTBOUND_PROVIDER
        if "model_name" in template and isinstance(template["model_name"], dict):
            template["model_name"]["value"] = DEFAULT_OUTBOUND_MODEL


def _bind_knowledge_base(payload: dict[str, Any], kb_name: str) -> None:
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") != "Knowledge":
            continue
        template = (data.get("node") or {}).get("template") or {}
        for key in ("knowledge_base", "kb_name", "name"):
            field = template.get(key)
            if isinstance(field, dict) and "value" in field:
                field["value"] = kb_name


def _inject_deterministic_embeddings_hook(payload: dict[str, Any]) -> None:
    """Append component-local embedding overrides without mutating shared modules."""
    hook = """
# --- perf suite stub: deterministic embeddings (no vendor HTTP) ---
import hashlib as _perf_hashlib

PERF_MOCK_EMBEDDING_MARKER = "PERF_MOCK_EMBEDDING"

class _PerfDeterministicEmbeddings:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str):
        values = []
        block = 0
        while len(values) < self.dimension:
            digest = _perf_hashlib.sha256(f"{block}:{text}".encode()).digest()
            values.extend(byte / 255.0 for byte in digest)
            block += 1
        return values[:self.dimension]

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str):
        return self._embed(text)

def get_embeddings(*_args, **_kwargs):
    return _PerfDeterministicEmbeddings()

if "MemoryBaseComponent" in globals():
    async def _perf_build_chroma(self, kb_path, owner, metadata, kb_name):
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        return Chroma(
            persist_directory=str(kb_path),
            embedding_function=_PerfDeterministicEmbeddings(),
            collection_name=kb_name,
            **chroma_langchain_collection_kwargs(),
        )

    MemoryBaseComponent._build_chroma = _perf_build_chroma
# --- end perf suite stub ---
"""
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") not in {"Knowledge", "MemoryBase"}:
            continue
        template = (data.get("node") or {}).get("template") or {}
        code = template.get("code")
        if not isinstance(code, dict):
            continue
        src = str(code.get("value") or "")
        if "perf suite stub: deterministic embeddings" in src:
            continue
        # Appending preserves the module docstring and ``from __future__`` placement.
        # Component methods resolve these module globals when they execute.
        code["value"] = src.rstrip() + "\n\n" + hook.lstrip()


def _inject_deterministic_agent_llm(payload: dict[str, Any], *, force_first_tool_call: bool) -> None:
    support = _read_component_source("perf_mock_agent.py").replace(
        "False  # __PERF_FORCE_FIRST_TOOL_CALL__",
        str(force_first_tool_call),
    )
    methods = """
    # Perf suite overrides: preserve the real Agent loop/history/tools and
    # replace only model selection/construction.
    def _resolve_selected_model(self):
        return _perf_model()

    def _get_llm(self):
        return _perf_model()
"""
    for node in _iter_nodes(payload):
        data = node.get("data") or {}
        if data.get("type") != "Agent":
            continue
        template = (data.get("node") or {}).get("template") or {}
        code = template.get("code")
        if not isinstance(code, dict):
            continue
        src = str(code.get("value") or "")
        if "_PerfToolAwareChatModel" in src:
            continue
        class_marker = "\nclass AgentComponent("
        if class_marker not in src:
            msg = "Natural Agent source is missing class AgentComponent"
            raise ValueError(msg)
        with_support = src.replace(class_marker, f"\n\n{support.rstrip()}\n\nclass AgentComponent(", 1)
        code["value"] = with_support.rstrip() + "\n" + methods


def load_starter(shape: str) -> dict[str, Any]:
    filename = SHAPE_STARTERS[shape]
    path = STARTERS_DIR / filename
    if not path.exists():
        msg = f"starter missing for natural shape {shape}: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def adapt_natural_starter(shape: str, *, stubbed: bool, kb_name: str = DEFAULT_KB_NAME) -> dict[str, Any]:
    """Pin starter topology; stub only vendor LLM / web / URL / embedding edges when stubbed."""
    payload = load_starter(shape)
    mode = "stubbed" if stubbed else "live"
    fid = f"natural_{shape}__external_{mode}"
    payload["name"] = fid
    payload["description"] = f"Natural {shape} from starter {SHAPE_STARTERS[shape]}; external_apis={mode}."
    payload["endpoint_name"] = fid.replace("_", "-")
    payload["tags"] = sorted(set(payload.get("tags") or []) | {"performance-suite", "natural"})
    payload["is_component"] = False
    payload.pop("id", None)
    _drop_note_nodes(payload)
    _set_chat_store_flags(payload, store=(shape == "memory_chatbot"))

    if stubbed:
        _replace_code_for_types(
            payload,
            {"LanguageModelComponent"},
            _read_component_source("perf_mock_language_model.py"),
        )
        _inject_deterministic_agent_llm(payload, force_first_tool_call=shape == "memory_chatbot")
        _replace_code_for_types(payload, {"URLComponent"}, _read_component_source("perf_mock_url.py"))
        _replace_code_for_types(
            payload,
            {"UnifiedWebSearch"},
            _read_component_source("perf_mock_web_search.py"),
        )
        _inject_deterministic_embeddings_hook(payload)
    else:
        _bind_live_llm(payload)

    if shape == "vector_store_rag":
        _bind_knowledge_base(payload, kb_name)

    assert_topology(shape, payload)
    return payload
