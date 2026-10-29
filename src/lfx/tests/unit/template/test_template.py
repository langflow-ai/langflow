"""Template collection keys must not shadow component input names."""

from lfx.io import MessageTextInput
from lfx.template.template.base import Template


def test_component_input_named_fields_survives_template_round_trip():
    data = {
        "_type": "Component",
        "fields": MessageTextInput(name="fields", value="Name,Phone").to_dict(),
        "record_id": MessageTextInput(name="record_id", value="001000000000001AAA").to_dict(),
    }

    template = Template.from_dict(data)
    exported = template.to_dict()

    assert template.get_field("fields").value == "Name,Phone"
    assert exported["fields"]["value"] == "Name,Phone"
    assert exported["record_id"]["value"] == "001000000000001AAA"
    assert Template.from_dict(exported).get_field("fields").value == "Name,Phone"
