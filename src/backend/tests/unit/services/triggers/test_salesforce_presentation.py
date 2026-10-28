"""Trigger settings use the same human labels as the component palette."""

from langflow.services.triggers.providers.salesforce import PROVIDER
from lfx_salesforce.components import salesforce as components


def test_runtime_trigger_labels_match_the_palette():
    for kind in PROVIDER.kinds:
        assert kind.display_name == getattr(components, kind.component).display_name
