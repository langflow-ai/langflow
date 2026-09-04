"""Tests for lfx.utils.component_aliases.

The ext-key alias derivation is the regression surface: extension components
are keyed ``ext:<bundle>:<Class>@<slot>`` and their decorated templates carry
``name=None`` / ``_type="Component"``, so the bare legacy class name can only
come from parsing the key itself.  Without it, the starter-project updater
(and every other flatten_components_with_aliases consumer) stops resolving
pre-move node types like ``TavilySearchComponent``.
"""

import pytest
from lfx.utils.component_aliases import (
    build_component_identity_index,
    flatten_components_with_aliases,
    get_component_type_aliases,
)

EXT_KEY = "ext:tavily:TavilySearchComponent@official"

# The shape an ext component actually presents after template decoration:
# no ``name``, display_name is the human label, ``_type`` is the generic base.
EXT_COMPONENT_DATA = {
    "display_name": "Tavily Search API",
    "template": {"_type": "Component", "code": {"value": "code"}},
}


def test_ext_key_yields_bare_class_name_alias():
    aliases = get_component_type_aliases(EXT_KEY, EXT_COMPONENT_DATA)
    assert EXT_KEY in aliases
    assert "TavilySearchComponent" in aliases
    assert "TavilySearch" in aliases
    assert "TavilyAISearch" in aliases
    assert "TavilySearchToolComponent" in aliases


def test_ext_key_without_component_suffix_yields_only_class_name():
    aliases = get_component_type_aliases("ext:zep:ZepChatMemory@official", None)
    assert "ZepChatMemory" in aliases
    assert "" not in aliases


def test_non_ext_key_unaffected():
    aliases = get_component_type_aliases(
        "TavilySearchComponent",
        {"name": "TavilySearchComponent", "template": {"_type": "TavilySearchComponent"}},
    )
    assert aliases[0] == "TavilySearchComponent"
    assert not any(a.startswith("ext:") for a in aliases)


def test_flatten_resolves_legacy_type_for_ext_component():
    all_types_dict = {"tavily": {EXT_KEY: EXT_COMPONENT_DATA}}
    flat = flatten_components_with_aliases(all_types_dict)
    assert flat["TavilySearchComponent"] is flat[EXT_KEY]
    assert flat["TavilySearch"] is flat[EXT_KEY]
    assert flat["TavilyAISearch"] is flat[EXT_KEY]
    assert flat["TavilySearchToolComponent"] is flat[EXT_KEY]


def test_flatten_alias_never_overrides_real_key():
    in_tree = {"display_name": "In-tree", "template": {"_type": "TavilySearchComponent"}}
    all_types_dict = {
        "tools": {"TavilySearchComponent": in_tree},
        "tavily": {EXT_KEY: EXT_COMPONENT_DATA},
    }
    flat = flatten_components_with_aliases(all_types_dict)
    assert flat["TavilySearchComponent"] is in_tree


# Identity (class name) must beat another component's display_name regardless of
# registry iteration order.  Both the standalone ``AgentQL`` component (ext class
# name "AgentQL") and the Composio wrapper (display_name "AgentQL") contribute the
# "AgentQL" alias; only the standalone owns it as an identity.  When both moved to
# bundles, single-pass setdefault made the winner order-dependent and the Composio
# wrapper sometimes shadowed the real component, mismatching starter-project nodes.
_AGENTQL_STANDALONE = (
    "ext:agentql:AgentQL@official",
    {"display_name": "Extract Web Data", "template": {"_type": "Component"}},
)
_AGENTQL_COMPOSIO = (
    "ext:composio:ComposioAgentQLAPIComponent@official",
    {"display_name": "AgentQL", "template": {"_type": "Component"}},
)


def test_identity_alias_beats_display_name_collision_standalone_first():
    all_types_dict = {"c": dict([_AGENTQL_STANDALONE, _AGENTQL_COMPOSIO])}
    flat = flatten_components_with_aliases(all_types_dict)
    assert flat["AgentQL"] is flat[_AGENTQL_STANDALONE[0]]


def test_identity_alias_beats_display_name_collision_composio_first():
    # Reversed insertion order -- the case that was failing intermittently in CI.
    all_types_dict = {"c": dict([_AGENTQL_COMPOSIO, _AGENTQL_STANDALONE])}
    flat = flatten_components_with_aliases(all_types_dict)
    assert flat["AgentQL"] is flat[_AGENTQL_STANDALONE[0]]


ASTRADB_KEY = "ext:datastax:AstraDBVectorStoreComponent@official"  # pragma: allowlist secret
IDENTITY_COMPONENTS = {
    "models_and_agents": {
        "Prompt Template": {
            "name": "Prompt Template",
            "display_name": "Prompt Template",
            "metadata": {"module": "lfx.components.models_and_agents.prompt.PromptComponent"},
            "template": {"_type": "Component"},
        },
        "LangChain Hub Prompt": {
            "name": "LangChain Hub Prompt",
            "display_name": "Prompt Hub",
            "metadata": {"module": "lfx.components.langchain_utilities.langchain_hub.LangChainHubPromptComponent"},
            "template": {"_type": "Component"},
        },
    },
    "llm_operations": {
        "Smart Transform": {
            "name": "Smart Transform",
            "display_name": "Smart Transform",
            "metadata": {"module": "lfx.components.llm_operations.lambda_filter.LambdaFilterComponent"},
            "template": {"_type": "Component"},
        },
    },
    "input_output": {
        "ChatInput": {
            "display_name": "Chat Input",
            "metadata": {"module": "lfx.components.input_output.chat.ChatInput"},
            "template": {"_type": "Component"},
        }
    },
    "datastax": {
        ASTRADB_KEY: {
            "name": "AstraDB",
            "display_name": "Astra DB",
            "metadata": {"module": "lfx_datastax.components.datastax.astradb_vectorstore.AstraDBVectorStoreComponent"},
            "template": {"_type": "Component"},
        }
    },
}


@pytest.mark.parametrize(
    ("identity", "canonical"),
    [
        ("Prompt Template", "Prompt Template"),
        ("Prompt", "Prompt Template"),
        ("PromptComponent", "Prompt Template"),
        (ASTRADB_KEY, ASTRADB_KEY),
        ("AstraDB", ASTRADB_KEY),
        ("AstraDBVectorStoreComponent", ASTRADB_KEY),
        ("AstraDBVectorStore", ASTRADB_KEY),
        ("ChatInput", "ChatInput"),
        ("Chat Input", "ChatInput"),
        ("LambdaFilter", "Smart Transform"),
        ("LambdaFilterComponent", "Smart Transform"),
        ("LangChainHubPrompt", "LangChain Hub Prompt"),
        ("LangChainHubPromptComponent", "LangChain Hub Prompt"),
    ],
)
def test_component_identity_index_resolves_current_and_legacy_identities(identity, canonical):
    identity_index = build_component_identity_index(IDENTITY_COMPONENTS)
    assert identity_index.resolve(identity) == frozenset({canonical})


def test_component_identity_index_keeps_same_tier_collisions_ambiguous():
    components = {
        "one": {"First": {"name": "Shared"}},
        "two": {"Second": {"name": "Shared"}},
    }
    identity_index = build_component_identity_index(components)
    assert identity_index.resolve("Shared") == frozenset({"First", "Second"})


def test_component_identity_index_canonical_and_identity_tiers_win_without_first_wins():
    identity_index = build_component_identity_index(
        {
            "canonical": {"AgentQL": {"display_name": "Canonical"}},
            "extensions": dict([_AGENTQL_COMPOSIO, _AGENTQL_STANDALONE]),
        }
    )

    # An exact registry key wins over every alias with the same spelling.
    assert identity_index.resolve("AgentQL") == frozenset({"AgentQL"})

    extension_only_index = build_component_identity_index(
        {"extensions": dict([_AGENTQL_COMPOSIO, _AGENTQL_STANDALONE])}
    )
    # The standalone class identity wins over the Composio display label,
    # independent of iteration order.
    assert extension_only_index.resolve("AgentQL") == frozenset({_AGENTQL_STANDALONE[0]})


def test_component_identity_index_preserves_unknown_exact_identity():
    identity_index = build_component_identity_index(IDENTITY_COMPONENTS)
    assert identity_index.resolve("UnknownComponent") == frozenset({"UnknownComponent"})
