import json

from langchain_community.utilities.jira import JiraAPIWrapper

from langflow.custom import Component
from langflow.io import BoolInput, Output, SecretStrInput, StrInput


class JiraIssueCreateComponent(Component):
    display_name = "JIRA Component"
    description = "Perform various JIRA operations"
    trace_type = "tool"
    icon = "JIRA"
    name = "Jira"

    inputs = [
        StrInput(
            name="instance_url",
            display_name="Instance URL",
            required=True,
            info="The base URL of the JIRA instance. Example: https://<company>.atlassian.net",
        ),
        StrInput(
            name="username",
            display_name="Username",
            required=True,
            info="Atlassian User E-mail. Example: email@example.com",
        ),
        SecretStrInput(
            name="api_token",
            display_name="API Token",
            required=True,
            info="Atlassian API Token. Create at: https://id.atlassian.com/manage-profile/security/api-tokens",
        ),
        BoolInput(
            name="cloud",
            display_name="Use Cloud?",
            required=True,
            value=True,
        ),
        StrInput(
            name="project_key",
            display_name="Project Key",
            required=False,
            info="Required for create and update operations",
        ),
        StrInput(
            name="issue_type",
            display_name="Issue Type",
            required=False,
            value="Bug",
            info="Required for create and update operations",
        ),
        StrInput(
            name="summary",
            display_name="Summary",
            required=False,
            info="Required for create and update operations",
        ),
        StrInput(
            name="description",
            display_name="Description",
            required=False,
            info="Required for create and update operations",
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="create_issue"),
    ]

    def build_jira(self) -> JiraAPIWrapper:
        return JiraAPIWrapper(
            jira_username=self.username,
            jira_api_token=self.api_token,
            jira_instance_url=self.instance_url,
            jira_cloud=str(self.cloud),
        )

    def create_issue(self) -> dict:
        jira = self.build_jira()

        fields = {"summary": self.summary, "project": {"key": self.project_key}, "issuetype": {"name": self.issue_type}}

        if self.description:  # description değeri dolu ise
            fields["description"] = self.description

        issue_data = json.dumps(fields)
        issue = jira.issue_create(issue_data)
        return issue
