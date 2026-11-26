"""Example third-party package. No Langflow imports or registration side effects."""

from lfx.inputs.inputs import MultilineInput
from lfx.projects import FieldTarget, ProjectTypeDefinition, ProjectTypeField, get_slot


class SupportDeskType(ProjectTypeDefinition):
    name = "support-desk"
    display_name = "Support desk"
    icon = "Headset"
    description = "Triage incoming support requests."
    fields = (
        ProjectTypeField(
            name="instructions",
            section="Instructions",
            input=MultilineInput(name="instructions", display_name="Instructions", value="Help the customer."),
            writes_to=FieldTarget("Agent", "system_prompt"),
            slot_definition=get_slot("Instructions"),
            supports_flow_binding=True,
        ),
    )


class OperatorSupportDeskType(SupportDeskType):
    display_name = "Operator's support desk"
