"""Declare a signed GitLab project webhook trigger."""

from lfx_gitlab.triggers import GitLabProjectTriggerComponent, trigger_inputs


class GitLabOnMergeRequestTriggerComponent(GitLabProjectTriggerComponent):
    display_name = "GitLab On Merge Request"
    name = "GitLabOnMergeRequestTriggerComponent"
    description = "Start the flow for selected signed project events."
    trigger_kind = "gitlab.merge_request"
    inputs = trigger_inputs("merge_request")
