module.exports = {
  docs: [
    "Get-Started/welcome-to-langflow",
    {
      type: "category",
      label: "Get started",
      items: [
        "Get-Started/get-started-installation",
        "Get-Started/get-started-quickstart",
      ],
    },
    {
      type: "category",
      label: "Starter projects",
      items: [
        'Starter-Projects/starter-projects-basic-prompting',
        'Starter-Projects/starter-projects-vector-store-rag',
        'Starter-Projects/starter-projects-simple-agent',
      ],
    },
    {
      type: "category",
      label: "Sample flows",
      items: [
        'Sample-Flows/blog-writer',
        'Sample-Flows/document-qa',
        'Sample-Flows/memory-chatbot',
        'Sample-Flows/sequential-agent',
        'Sample-Flows/travel-planning-agent',
      ],
    },
    {
      type: "category",
      label: "Concepts",
      items: [
        "Concepts/concepts-overview",
        "Concepts/concepts-playground",
        "Concepts/concepts-components",
        "Concepts/concepts-flows",
        "Concepts/concepts-objects",
        "Concepts/concepts-publish",
        "Concepts/concepts-file-management",
        "Concepts/concepts-voice-mode",
      ],
    },
    {
      type: "category",
      label: "Components",
      items: [
        "Components/components-agents",
        "Components/components-bundles",
        "Components/components-custom-components",
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
        "Configuration/configuration-cli",
        "Configuration/configuration-custom-database",
        "Configuration/configuration-global-variables",
        "Configuration/environment-variables",
      ],
    },
    {
      type: "category",
      label: "Develop",
      items: [
        "Develop/develop-overview",
        "Develop/develop-application",
        "Develop/install-custom-dependencies",
        "Develop/memory",
        "Develop/session-id",
        "Develop/logging",
        "Develop/webhook",
      ],
    },
    {
      type: "category",
      label: "Deployment",
      items: [
        {
          type:"doc",
          id: "Deployment/deployment-overview",
          label: "Deployment overview"
        },
        {
          type: "doc",
          id: "Deployment/deployment-docker",
          label: "Docker"
        },
        {
          type: "doc",
          id: "Deployment/deployment-kubernetes",
          label: "Kubernetes"
        },
        {
          type: "doc",
          id: "Deployment/deployment-gcp",
          label: "Google Cloud Platform"
        },
        {
          type: "doc",
          id: "Deployment/deployment-hugging-face-spaces",
          label: "Hugging Face Spaces"
        },
        {
          type: "doc",
          id: "Deployment/deployment-railway",
          label: "Railway"
        },
        {
          type: "doc",
          id: "Deployment/deployment-render",
          label: "Render"
        }
      ],
    },
    {
      type: "category",
      label: "API reference",
      items: [
        {
          type: "link",
          label: "API documentation",
          href: "/api",
        },
        {
          type: "doc",
          id: "API-Reference/api-reference-api-examples",
          label: "API examples",
        },
      ],
    },
    {
      type: "category",
      label: "Integrations",
      items: [
        {
          type: 'category',
          label: 'MCP (Model Context Protocol)',
          items: [
            'Integrations/MCP/integrations-mcp',
            'Integrations/MCP/mcp-component-astra',
          ],
        },
        "Integrations/Apify/integrations-apify",
        {
          type: "doc",
          id: "Integrations/Arize/integrations-arize",
          label: "Arize",
        },
        "Integrations/integrations-assemblyai",
        {
          type: "doc",
          id: "Integrations/Composio/integrations-composio",
          label: "Composio",
        },
        {
          type: 'category',
          label: 'Google',
          items: [
            'Integrations/Google/integrations-setup-google-oauth-langflow',
            'Integrations/Google/integrations-setup-google-cloud-vertex-ai-langflow',
          ],
        },
        "Integrations/integrations-langfuse",
        "Integrations/integrations-langsmith",
        "Integrations/integrations-langwatch",
        "Integrations/integrations-opik",
        {
          type: "category",
          label: "Notion",
          items: [
            "Integrations/Notion/integrations-notion",
            "Integrations/Notion/notion-agent-conversational",
            "Integrations/Notion/notion-agent-meeting-notes",
          ],
        },
        {
          type: "category",
          label: "NVIDIA",
          items: [
            "Integrations/Nvidia/integrations-nvidia-ingest",
            "Integrations/Nvidia/integrations-nvidia-nim-wsl2",
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
        "Contributing/contributing-component-tests",
        "Contributing/contributing-github-discussion-board",
        "Contributing/contributing-github-issues",
        "Contributing/contributing-how-to-contribute",
        "Contributing/contributing-telemetry",
      ],
    },
    {
      type: "category",
      label: "Changelog",
      items: [
        {
          type: "link",
          label: "Changelog",
          href: "https://github.com/langflow-ai/langflow/releases/latest",
        },
      ],
    },
    {
      type: "category",
      label: "Support",
      items: [
        {
          type: "doc",
          id: "Support/luna-for-langflow",
          label: "Luna for Langflow",
        },
      ],
    },
    {
      type: "html",
      className: "sidebar-ad",
      value: `
        <a href="https://astra.datastax.com/signup?type=langflow" target="_blank" class="menu__link">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-cloud"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>
          <div class="sidebar-ad-text-container">
            <span class="sidebar-ad-text">Use Langflow in the cloud</span>
            <span class="sidebar-ad-text sidebar-ad-text-gradient">Sign up for DataStax Langflow</span>
          </div>
        </a>
      `,
    },
  ],
};
