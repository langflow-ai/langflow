"""Stable GitLab component identities."""

from .issue_comment_create import GitLabCreateIssueCommentComponent
from .issue_create import GitLabCreateIssueComponent
from .issue_get import GitLabGetIssueComponent
from .issue_trigger import GitLabOnIssueTriggerComponent
from .issue_update import GitLabUpdateIssueComponent
from .merge_request_comment_create import GitLabCreateMergeRequestCommentComponent
from .merge_request_create import GitLabCreateMergeRequestComponent
from .merge_request_get import GitLabGetMergeRequestComponent
from .merge_request_trigger import GitLabOnMergeRequestTriggerComponent
from .merge_request_update import GitLabUpdateMergeRequestComponent
from .project_get import GitLabGetProjectComponent

__all__ = [
    "GitLabCreateIssueCommentComponent",
    "GitLabCreateIssueComponent",
    "GitLabCreateMergeRequestCommentComponent",
    "GitLabCreateMergeRequestComponent",
    "GitLabGetIssueComponent",
    "GitLabGetMergeRequestComponent",
    "GitLabGetProjectComponent",
    "GitLabOnIssueTriggerComponent",
    "GitLabOnMergeRequestTriggerComponent",
    "GitLabUpdateIssueComponent",
    "GitLabUpdateMergeRequestComponent",
]
