module.exports = {
  docs: [
    "Get-Started/welcome-to-langflow",
    {
      type: "category",
      label: "Get Started",
      items: [
        "Get-Started/get-started-installation",
        "Get-Started/get-started-quickstart",
      ],
    },
    {
      type: "category",
      label: "Starter Projects",
      items: [
        'Starter-Projects/starter-projects-basic-prompting',
        'Starter-Projects/starter-projects-vector-store-rag',
        'Starter-Projects/starter-projects-simple-agent',
      ],
    },
    {
      type: "category",
      label: "Tutorials",
      items: [
        'Tutorials/tutorials-blog-writer',
        'Tutorials/tutorials-document-qa',
        'Tutorials/tutorials-memory-chatbot',
        'Tutorials/tutorials-sequential-agent',
        'Tutorials/tutorials-travel-planning-agent',
      ],
    },
    {
      type: "category",
      label: "Workspace",
      items: [
        "Workspace/workspace-overview",
        "Workspace/workspace-api",
        "Workspace/workspace-logs",
        "Workspace/workspace-playground",
      ],
    },
    {
      type: "category",
      label: "Components",
      items: [
        "Components/components-overview",
        "Components/components-agents",
        "Components/components-data",
        "Components/components-embedding-models",
        "Components/components-helpers",
        "Components/components-io",
        "Components/components-loaders",
        "Components/components-logic",
        "Components/components-memories",
        "Components/components-models",
        "Components/components-processing",
        "Components/components-prompts",
        "Components/components-tools",
        "Components/components-vector-stores",
        "Components/components-custom-components",
      ],
    },
    {
      type: "category",
      label: "Agents",
      items: [
        "Agents/agents-overview",
        "Agents/agent-tool-calling-agent-component",
      ],
    },
    {
      type: "category",
      label: "Configuration",
      items: [
        "Configuration/configuration-api-keys",
        "Configuration/configuration-authentication",
        "Configuration/configuration-auto-saving",
        "Configuration/configuration-backend-only",
        "Configuration/configuration-cli",
        "Configuration/configuration-global-variables",
        "Configuration/environment-variables",
        "Configuration/configuration-objects",
        "Configuration/configuration-security-best-practices"
      ],
    },
    {
      type: "category",
      label: "Deployment",
      items: [
        "Deployment/deployment-docker",
        "Deployment/deployment-gcp",
        "Deployment/deployment-hugging-face-spaces",
        "Deployment/deployment-kubernetes",
        "Deployment/deployment-railway",
        "Deployment/deployment-render",
      ],
    },
    {
      type: "category",
      label: "Integrations",
      items: [
        "Integrations/integrations-assemblyai",
        "Integrations/Composio/integrations-composio",
        "Integrations/integrations-langfuse",
        "Integrations/integrations-langsmith",
        "Integrations/integrations-langwatch",
        {
          type: 'category',
          label: 'Google',
          items: [
            'Integrations/Google/integrations-setup-google-oauth-langflow',
            'Integrations/Google/integrations-setup-google-cloud-vertex-ai-langflow',
          ],
        },
        {
          type: "category",
          label: "Notion",
          items: [
            "Integrations/Notion/integrations-notion",
            "Integrations/Notion/notion-agent-conversational",
            "Integrations/Notion/notion-agent-meeting-notes",
          ],
        },
      ],
    },
    {
      type: "category",
      label: "Contributing",
      items: [
        "Contributing/contributing-community",
        "Contributing/contributing-components",
        "Contributing/contributing-github-discussion-board",
        "Contributing/contributing-github-issues",
        "Contributing/contributing-how-to-contribute",
        "Contributing/contributing-telemetry",
      ],
    },
    {
      type: "category",
      label: "API Reference",
      items: [
        {
          type: "link",
          label: "API Documentation",
          href: "/api",
        },
      ],
    },
  ],
};
