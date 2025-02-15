import json
from langchain_community.utilities.jira import JiraAPIWrapper
from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, BoolInput, Output, DropdownInput

class JiraIssueSearchComponent(Component):
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
        DropdownInput(
            name="operation",
            display_name="Operation",
            required=True,
            value="create",
            info="Operation to perform: create, search",
            options=["create", "search"],
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
            value="Task",
            info="Required for create and update operations",
        ),
        StrInput(
            name="summary",
            display_name="Summary",
            required=False,
            info="Required for create and update operations",
        ),
        StrInput(
            name="issue_key",
            display_name="Issue Key",
            required=False,
            info="Required for update, get, and delete operations",
        ),
        StrInput(
            name="jql_query",
            display_name="JQL Query",
            required=False,
            info="Required for search operations. Example: 'project = TEST AND status = Open'",
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="search_issues"),
    ]

    def build_jira(self) -> JiraAPIWrapper:
        return JiraAPIWrapper(
            jira_username=self.username,
            jira_api_token=self.api_token,
            jira_instance_url=self.instance_url,
            jira_cloud=str(self.cloud)
        )


    def search_issues(self) -> dict:
        jira = self.build_jira()
        jql = self.jql_query or ""
        conditions = []
        
        if self.issue_key:
            conditions.append(f'key="{self.issue_key}"')
        if self.project_key:
            conditions.append(f'project="{self.project_key}"')
        if self.summary:
            conditions.append(f'summary~"{self.summary}"')
        if self.issue_type:
            conditions.append(f'issuetype="{self.issue_type}"')
        
        if conditions:
            dynamic_jql = " AND ".join(conditions)
            if jql:
                jql = f"{jql} AND {dynamic_jql}"
            else:
                jql = dynamic_jql
        result = jira.search(jql)
        return result