import importlib

import pytest


def test_deprecated_astra_assistants_removed():
    """Deprecated Astra Assistants components should not be exported by the Datastax bundle."""
    import lfx.components.datastax as datastax

    removed_components = [
        "AssistantsCreateAssistant",
        "AssistantsCreateThread",
        "AssistantsGetAssistantName",
        "AssistantsListAssistants",
        "AssistantsRun",
        "AstraAssistantManager",
    ]

    for name in removed_components:
        assert not hasattr(datastax, name), f"Deprecated component {name} should have been removed"


def test_datastax_remaining_components_accessible():
    """Non-deprecated Datastax components should remain exported by the Datastax bundle."""
    import lfx.components.datastax as datastax

    expected_components = [
        "AstraDBVectorStoreComponent",
        "AstraDBChatMemory",
        "AstraDBToolComponent",
        "AstraDBCQLToolComponent",
        "AstraDBGraphVectorStoreComponent",
        "AstraVectorizeComponent",
        "GraphRAGComponent",
        "Dotenv",
    ]

    for name in expected_components:
        assert hasattr(datastax, name), f"Component {name} should still be accessible"
        component = getattr(datastax, name)
        assert component is not None, f"Component {name} should not be None"


def test_getenvvar_component_removed():
    """The removed GetEnvVar component should not be importable from the Datastax bundle."""
    import lfx.components.datastax as datastax

    with pytest.raises(AttributeError):
        _ = datastax.GetEnvVar

    assert not hasattr(datastax, "GetEnvVar"), "GetEnvVar should have been removed from lfx.components.datastax"

    with pytest.raises((ImportError, ModuleNotFoundError)):
        importlib.import_module("lfx_datastax.components.datastax.getenvvar")


def test_datastax_dir_excludes_deprecated():
    """dir(datastax) should not list deprecated components."""
    import lfx.components.datastax as datastax

    exported = dir(datastax)
    deprecated = {
        "AssistantsCreateAssistant",
        "AssistantsCreateThread",
        "AssistantsGetAssistantName",
        "AssistantsListAssistants",
        "AssistantsRun",
        "AstraAssistantManager",
    }

    assert not deprecated.intersection(exported), (
        f"Deprecated components still appear in dir(): {deprecated.intersection(exported)}"
    )
