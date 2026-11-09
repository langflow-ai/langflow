# Jira Cloud

This preview bundle provides search, read, create, update and workflow transition actions. Triggers support at most 5000 matching visible or retained issue IDs per baseline. An optional issue-type filter narrows large projects. Intermediate edits and transitions can be missed.

Its three triggers observe new issues, changed issue states and changed statuses through authenticated project snapshots.

See the [Jira Cloud setup guide](https://docs.langflow.org/next/bundles-jira) for the capability matrix, Atlassian app registration, connection setup, background runs, event identity, and recovery. The [guide source](../../../docs/docs/Components/bundles-jira.mdx) is included in this repository.

Install this wheel alongside Langflow 1.14 with the matching server runtime. Actions support hosted and self-managed servers. Triggers require a self-managed server and a running Langflow listener. Standalone lfx can import the components and manifest, but running Jira flows through headless lfx is unsupported. Langflow Desktop and Jira Data Center are also unsupported.
