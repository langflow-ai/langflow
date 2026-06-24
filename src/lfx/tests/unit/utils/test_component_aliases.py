"""Tests for lfx.utils.component_aliases.

The ext-key alias derivation is the regression surface: extension components
are keyed ``ext:<bundle>:<Class>@<slot>`` and their decorated templates carry
``name=None`` / ``_type="Component"``, so the bare legacy class name can only
come from parsing the key itself.  Without it, the starter-project updater
(and every other flatten_components_with_aliases consumer) stops resolving
pre-move node types like ``TavilySearchComponent``.
"""

from lfx.utils.component_aliases import (
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
