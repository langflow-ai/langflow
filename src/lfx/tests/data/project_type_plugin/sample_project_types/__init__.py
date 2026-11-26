"""Example third-party package. No Langflow imports or registration side effects."""

from lfx.inputs.inputs import MultilineInput
from lfx.projects import FieldTarget, ProjectTypeDefinition, ProjectTypeField, get_slot


class SupportDeskType(ProjectTypeDefinition):
    name = "support-desk"
    display_name = "Support desk"
    icon = "Headset"
    description = "Triage incoming support requests."
    allows_empty_project = True
    panels = ("reports",)
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

    async def save_config(self, request, ctx):
        from uuid import UUID

        from lfx.projects.lifecycle import FlowSelector, PreparedSave, ProjectConfigError

        if request.config is None:
            return PreparedSave(None)
        config = dict(request.config)
        if "instructions" in config:
            config["instructions"] = config["instructions"].strip()
            if not config["instructions"]:
                msg = "Write support instructions before saving."
                raise ProjectConfigError(msg, field_path="instructions")
        if config.get("source_id"):
            source = await ctx.read_flow(FlowSelector(id=UUID(config["source_id"])), access="execute")
            (snapshot,) = await ctx.pin_sources((source.token,), label="support reference")
            config["source_version"] = str(snapshot.reference.version_id)
        return PreparedSave(config, tuple(flow.id for flow in request.flows))


class OperatorSupportDeskType(SupportDeskType):
    display_name = "Operator's support desk"
