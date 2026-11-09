"""Trigger settings use the same human labels as the component palette."""

from langflow.services.triggers.providers.gitlab.runtime import PROVIDER
from lfx_gitlab.components import gitlab as components


def test_runtime_trigger_labels_match_the_palette():
    for kind in PROVIDER.kinds:
        assert kind.display_name == getattr(components, kind.component).display_name
