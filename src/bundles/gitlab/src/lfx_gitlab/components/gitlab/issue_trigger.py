"""Declare a signed GitLab project webhook trigger."""

from lfx_gitlab.triggers import GitLabProjectTriggerComponent, trigger_inputs


class GitLabOnIssueTriggerComponent(GitLabProjectTriggerComponent):
    display_name = "GitLab On Issue"
    name = "GitLabOnIssueTriggerComponent"
    description = "Start the flow for selected signed project events."
    trigger_kind = "gitlab.issue"
    inputs = trigger_inputs("issue")
