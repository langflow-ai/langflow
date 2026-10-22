# Jira Cloud

This preview bundle provides search, read, create, update and workflow transition actions. Triggers support at most 5000 matching visible or retained issue IDs per baseline. An optional issue-type filter narrows large projects. Intermediate edits and transitions can be missed.

Its three triggers observe new issues, changed issue states and changed statuses through authenticated project snapshots.

The server runtime requires the provider runtime prerequisite in PR 15947. See [setup and recovery](../../../design/provider-integrations/jira.md) for the deployment matrix and delivery limits.

Install this wheel alongside Langflow 1.14 with the matching server runtime. Standalone lfx imports the components and manifest without importing Langflow. The server discovers its adapter through the installed distribution entry point.
