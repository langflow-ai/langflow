"""Build real palette templates for every exported bundle component."""

import pytest
from lfx.custom.utils import create_component_template
from lfx_gitlab.components import gitlab as components


@pytest.mark.parametrize("class_name", components.__all__)
def test_exported_component_builds_its_own_palette_template(class_name):
    component_class = getattr(components, class_name)
    component = component_class()

    template, instance = create_component_template(
        component_extractor=component, module_name=component_class.__module__
    )

    assert type(instance) is component_class
    assert template["metadata"]["component_class_name"] == class_name
    assert template["display_name"] == component.display_name
    assert [output["name"] for output in template["outputs"]] == [output.name for output in component.outputs]
    assert {item.name for item in component.inputs} <= template["template"].keys()
