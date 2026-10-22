"""Declare a signed GitLab project webhook trigger."""

from lfx_gitlab.triggers import GitLabProjectTrigger, trigger_inputs


class GitLabOnMergeRequestTriggerComponent(GitLabProjectTrigger):
    display_name = "GitLab On Merge Request"
    name = "GitLabOnMergeRequestTriggerComponent"
    description = "Start the flow for selected signed project events."
    trigger_kind = "gitlab.merge_request"
    inputs = trigger_inputs("merge_request")
