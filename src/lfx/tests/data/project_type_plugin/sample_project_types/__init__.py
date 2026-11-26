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

    def starters(self):
        from lfx.projects.starters import ProjectStarter

        return (ProjectStarter("support-inbox", "Support inbox", "Start a support project.", build_support_inbox),)

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
            config["source_revision"] = snapshot.reference.revision
        return PreparedSave(config, tuple(flow.id for flow in request.flows))

    def archive_sources(self, config):
        from uuid import UUID

        from lfx.projects.lifecycle import SourceVersionReference

        if not (config or {}).get("source_id"):
            return ()
        return (
            SourceVersionReference(
                UUID(config["source_id"]),
                UUID(config["source_version"]),
                config["source_revision"],
            ),
        )

    def validate_archive(self, config, ctx):
        from lfx.projects.bindings import flow_revision

        for reference in self.archive_sources(config):
            if flow_revision(ctx.source(str(reference.flow_id))["data"]) != reference.revision:
                msg = "The support reference changed. Review it before exporting."
                raise ValueError(msg)

    def export_config(self, config, mapping):
        from lfx.projects.bindings import flow_revision

        config = super().export_config(config, mapping)
        if (config or {}).get("source_id"):
            original = config["source_id"]
            config["source_id"] = mapping.flow_ids[original]
            config["source_version"] = mapping.version_ids[original]
            config["source_revision"] = flow_revision(mapping.source(original)["data"])
        return config

    def import_config(self, config, mapping):
        return self.export_config(config, mapping)


class OperatorSupportDeskType(SupportDeskType):
    display_name = "Operator's support desk"


def build_support_inbox():
    from uuid import UUID

    from lfx.projects.archives import ArchivedProject, ProjectComposition

    project_id = UUID("50b2718f-aae3-46e0-b782-6e35bcd9c943")
    return ProjectComposition(
        root_project_id=project_id,
        projects=[
            ArchivedProject(
                id=project_id,
                name="Support inbox",
                project_type=SupportDeskType.name,
                project_config={"instructions": "Help the customer."},
                flows=[],
            )
        ],
    )
