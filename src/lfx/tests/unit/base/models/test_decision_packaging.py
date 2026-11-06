"""Release guards for how decision models ship: provider-free, indexed, and with every mandatory provider."""

import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED
from lfx.base.models.decisions import providers
from lfx.custom.utils import _generate_code_hash
from lfx.interface.components import _read_component_index

MANDATORY_PROVIDERS = {"TypeSafe", "Perplexity", "OpenAI"}
DECISION_MODULES = (
    "lfx.base.models.decision_constants",
    "lfx.base.models.decisions.schema",
    "lfx.base.models.decisions.providers",
    "lfx.base.models.decisions.runtime",
    "lfx.components.llm_operations.decision_model",
    "lfx.components.llm_operations.llm_conditional_router",
)
# Top-level names of provider SDKs and their LangChain wrappers. Decisions talk to documented HTTP
# endpoints through httpx, so the provider-free core never needs one installed.
PROVIDER_SDKS = frozenset(
    {
        "anthropic",
        "boto3",
        "cohere",
        "google",
        "groq",
        "ibm_watsonx_ai",
        "langchain_anthropic",
        "langchain_google_genai",
        "langchain_ollama",
        "langchain_openai",
        "mistralai",
        "ollama",
        "openai",
        "perplexity",
        "perplexityai",
        "typesafe",
    }
)
# Decision code that is decision-only; the router also serves Language Model mode, whose model
# loading is checked by the import test below rather than statically.
DECISION_ONLY_MODULES = DECISION_MODULES[:-1]
INDEXED_FIELDS = {
    "DecisionModel": {"model", "kind", "context", "question", "candidates", "structured_context", "timeout"},
    "SmartRouter": {
        "routing_mode",
        "decision_model",
        "decision_kind",
        "decision_question",
        "minimum_probability",
        "evaluation_error_action",
        "score_levels",
        "enable_else_output",
    },
}


def test_every_mandatory_provider_is_offered_and_reachable():
    """A release can't silently drop a provider: each has catalog rows and an endpoint."""
    catalog = {row["provider"] for row in DECISION_MODELS_DETAILED}
    assert catalog == MANDATORY_PROVIDERS
    assert set(providers.ENDPOINTS) == MANDATORY_PROVIDERS
    for provider in MANDATORY_PROVIDERS:
        capabilities = [set(row["capabilities"]) for row in DECISION_MODELS_DETAILED if row["provider"] == provider]
        assert {"choice", "boolean", "score"} in capabilities, f"{provider} has no model offering every type"


def test_importing_the_decision_path_loads_no_provider_sdk():
    """Checked in a fresh interpreter, so another test's imports can't hide or cause a failure.

    A finder on ``sys.meta_path`` records every attempt to import a provider SDK, so the check holds
    whether or not the SDK is installed where the tests run; provider-free lanes don't install any.
    """
    script = (
        "import sys\n"
        "attempted = set()\n"
        "class RecordProviderImports:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        f"        if name.split('.')[0] in {sorted(PROVIDER_SDKS)!r}:\n"
        "            attempted.add(name.split('.')[0])\n"
        "sys.meta_path.insert(0, RecordProviderImports())\n"
        f"for name in {list(DECISION_MODULES)!r}:\n"
        "    __import__(name)\n"
        "print(','.join(sorted(attempted | {module.split('.')[0] for module in sys.modules})))\n"
    )
    loaded = (
        subprocess.run(  # noqa: S603 - fixed interpreter and script
            [sys.executable, "-I", "-c", script], capture_output=True, text=True, check=True, timeout=120
        )
        .stdout.strip()
        .rsplit("\n", 1)[-1]
    )

    assert set(loaded.split(",")) & PROVIDER_SDKS == set()


@pytest.mark.parametrize("module_name", DECISION_ONLY_MODULES)
def test_decision_sources_never_import_a_provider_sdk(module_name):
    """Static, so an import inside a function that a test never reaches still counts."""
    tree = ast.parse(Path(importlib.import_module(module_name).__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    assert imported & PROVIDER_SDKS == set()


def _indexed(component_name):
    index = _read_component_index()
    assert index is not None, "LFX rejected its bundled component index"
    matches = [components[component_name] for _, components in index["entries"] if component_name in components]
    assert len(matches) == 1, f"{component_name} is indexed {len(matches)} times"
    return matches[0]


@pytest.mark.parametrize("component_name", sorted(INDEXED_FIELDS))
def test_the_bundled_index_ships_current_decision_components(component_name):
    entry = _indexed(component_name)
    module_name, class_name = entry["metadata"]["module"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    getattr(module, class_name)

    # A stale index would serve an older component to every install that doesn't load dynamically.
    assert entry["metadata"]["code_hash"] == _generate_code_hash(inspect.getsource(module), module_name), (
        "Rebuild the component index: make build_component_index"
    )
    assert INDEXED_FIELDS[component_name] <= set(entry["template"])
