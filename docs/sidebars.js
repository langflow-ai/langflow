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
        'Starter-Projects/starter-projects-blog-writer',
        'Starter-Projects/starter-projects-document-qa',
        'Starter-Projects/starter-projects-memory-chatbot',
        'Starter-Projects/starter-projects-simple-agent',
        'Starter-Projects/starter-projects-vector-store-rag',
        'Starter-Projects/starter-projects-sequential-agent',
        'Starter-Projects/starter-projects-travel-planning-agent',
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
        "Configuration/configuration-security-best-practices"
      ],
    },
    {
      type: "category",
      label: "Components",
      items: [
        "Components/components-overview",
        "Components/components-agents",
        "Components/components-custom-components",
        "Components/components-data",
        "Components/components-embedding-models",
        "Components/components-helpers",
        "Components/components-io",
        "Components/components-loaders",
        "Components/components-logic",
        "Components/components-memories",
        "Components/components-models",
        "Components/components-prompts",
        "Components/components-rag",
        "Components/components-tools",
        "Components/components-vector-stores",
      ],
    },
    {
      type: "category",
      label: "Guides",
      items: [
        "Guides/guides-chat-memory",
        "Guides/guides-data-message",
        "Guides/guides-new-to-llms",
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
