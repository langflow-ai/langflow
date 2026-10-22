"""Declare a signed GitLab project webhook trigger."""

from lfx_gitlab.triggers import GitLabProjectTrigger, trigger_inputs


class GitLabOnIssueTriggerComponent(GitLabProjectTrigger):
    display_name = "GitLab On Issue"
    name = "GitLabOnIssueTriggerComponent"
    description = "Start the flow for selected signed project events."
    trigger_kind = "gitlab.issue"
    inputs = trigger_inputs("issue")
