module.exports = {
  docs: [
    "Get-Started/welcome-to-langflow",
    {
      type: "category",
      label: "Get started",
      items: [
        {
          type: "doc",
          id: "Get-Started/about-langflow",
          label: "About Langflow"
        },
        {
          type: "doc",
          id: "Get-Started/get-started-installation",
          label: "Install Langflow"
        },
        {
          type: "doc",
          id: "Get-Started/get-started-quickstart",
          label: "Quickstart"
        },
        {
          type: "category",
          label: "Tutorials",
          items: [
            "Tutorials/chat-with-rag",
            "Tutorials/chat-with-files",
            "Tutorials/agent",
            "Tutorials/mcp-tutorial",
          ],
        },
      ],
    },
    {
      type: "category",
      label: "Templates",
      items: [
        'Templates/basic-prompting',
        'Templates/simple-agent',
        'Templates/blog-writer',
        'Templates/document-qa',
        'Templates/memory-chatbot',
        'Templates/vector-store-rag',
        'Templates/financial-report-parser',
        'Templates/sequential-agent',
        'Templates/travel-planning-agent',
      ],
    },
    {
      type: "category",
      label: "Flows",
      items: [
        {
          type: "doc",
          id: "Concepts/concepts-overview",
          label: "Use the visual editor"
        },
        {
          type: "doc",
          id: "Concepts/concepts-flows",
          label: "Build flows"
        },
        {
          type: "doc",
          id: "Concepts/concepts-publish",
          label: "Run flows"
        },
        {
          type: "doc",
          id: "Concepts/concepts-flows-import",
          label: "Import and export flows"
        },
        {
          type: "doc",
          id: "Concepts/concepts-playground",
          label: "Use the Playground"
        },
        {
          type: "doc",
          id: "Concepts/concepts-voice-mode",
          label: "Use voice mode"
        },
        {
          type: "doc",
          id: "Concepts/data-types",
          label: "Langflow data types"
        },
        {
          type: "doc",
          id: "Concepts/concepts-file-management",
          label: "Manage files"
        },
      ],
    },
    {
      type: "category",
      label: "Components",
      items: [
        "Concepts/concepts-components",
        "Components/components-agents",
        "Components/components-bundles",
        "Components/components-custom-components",
        "Components/components-data",
        "Components/components-embedding-models",
        "Components/components-helpers",
        "Components/components-io",
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
        "Agents/agents",
        "Agents/agents-tools",
      ],
    },
    {
      type: "category",
      label: "Model Context Protocol (MCP)",
      items: [
        "Concepts/mcp-server",
        "Components/mcp-client",
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
        "Contributing/contributing-telemetry",
      ],
    },
    {
      type: "category",
      label: "Develop",
      items: [
        {
          type: "doc",
          id: "Develop/develop-overview",
          label: "Overview"
        },
        {
          type: "doc",
          id: "Develop/develop-application",
          label: "Develop an application in Langflow"
        },
        {
          type: "doc",
          id: "Develop/install-custom-dependencies",
          label: "Install custom dependencies"
        },
        {
          type: "doc",
          id: "Develop/memory",
          label: "Memory management"
        },
        {
          type: "doc",
          id: "Develop/session-id",
          label: "Session ID"
        },
        {
          type: "doc",
          id: "Develop/logging",
          label: "Logging"
        },
        {
          type: "doc",
          id: "Develop/webhook",
          label: "Webhook"
        },
        {
          type: "category",
          label: "Clients",
          items: [
            {
              type: "doc",
              id: "Develop/Clients/typescript-client",
              label: "TypeScript Client"
            }
          ]
        },
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
          id: "Deployment/deployment-public-server",
          label: "Deploy a public Langflow server"
        },
        {
          type: "doc",
          id: "Deployment/deployment-caddyfile",
          label: "Deploy Langflow on a remote server"
        },
        {
          type: "category",
          label: "Kubernetes",
          items: [
            {
              type: "doc",
              id: "Deployment/deployment-prod-best-practices",
              label: "Langflow architecture and best practices"
            },
            {
              type: "doc",
              id: "Deployment/deployment-kubernetes-dev",
              label: "Deploy in development"
            },
            {
              type: "doc",
              id: "Deployment/deployment-kubernetes-prod",
              label: "Deploy in production"
            }
          ]
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
        },
      ],
    },
    {
      type: "category",
      label: "API reference",
      items: [
        {
          type: "doc",
          id: "API-Reference/api-reference-api-examples",
          label: "Get started with the Langflow API",
        },
        {
          type: "doc",
          id: "API-Reference/api-flows-run",
          label: "Flow trigger endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-flows",
          label: "Flow management endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-files",
          label: "Files endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-projects",
          label: "Projects endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-logs",
          label: "Logs endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-monitor",
          label: "Monitor endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-build",
          label: "Build endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-users",
          label: "Users endpoints",
        },
        {
          type: "link",
          label: "Langflow API specification",
          href: "/api",
        },
      ],
    },
    {
      type: "category",
      label: "Integrations",
      items: [
        "Integrations/Apify/integrations-apify",
        {
          type: "doc",
          id: "Integrations/Arize/integrations-arize",
          label: "Arize",
        },
        {
          type: "doc",
          id: "Integrations/integrations-assemblyai",
          label: "AssemblyAI",
        },
        {
          type: "doc",
          id: "Integrations/mcp-component-astra",
          label: "Astra DB MCP server",
        },
        {
          type: "doc",
          id: "Integrations/Cleanlab/integrations-cleanlab",
          label: "Cleanlab",
        },
        {
          type: "doc",
          id: "Integrations/Composio/integrations-composio",
          label: "Composio",
        },
        {
          type: "doc",
          id: "Integrations/Docling/integrations-docling",
          label: "Docling",
        },
        {
          type: 'category',
          label: 'Google',
          items: [
            'Integrations/Google/integrations-setup-google-cloud-vertex-ai-langflow',
            'Integrations/Google/integrations-google-big-query',
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
            {
              type: "doc",
              id: "Integrations/Nvidia/integrations-nvidia-ingest",
              label: "NVIDIA Ingest"
            },
            {
              type: "doc",
              id: "Integrations/Nvidia/integrations-nvidia-nim-wsl2",
              label: "NVIDIA NIM on WSL2"
            },
            {
              type: "doc",
              id: "Integrations/Nvidia/integrations-nvidia-g-assist",
              label: "NVIDIA G-Assist"
            },
          ],
        },
      ],
    },
    {
      type: "category",
      label: "Contribute",
      items: [
        "Contributing/contributing-community",
        "Contributing/contributing-how-to-contribute",
        "Contributing/contributing-components",
        "Contributing/contributing-component-tests",
        "Contributing/contributing-templates",
        "Contributing/contributing-bundles",
      ],
    },
    {
      type: "category",
      label: "Release notes",
      items: [
        {
          type: "doc",
          id: "Support/release-notes",
          label: "Release notes",
        },
      ],
    },
    {
      type: "category",
      label: "Support",
      items: [
        {
          type: "doc",
          id: "Support/troubleshooting",
          label: "Troubleshoot",
        },
        {
          type: "doc",
          id: "Contributing/contributing-github-issues",
          label: "Get help and request enhancements",
        },
        {
          type: "doc",
          id: "Support/luna-for-langflow",
          label: "Enterprise support",
        },
      ],
    },
    {
      type: "html",
      className: "sidebar-ad",
      value: `
        <a href="https://www.langflow.org/desktop" target="_blank" class="menu__link">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g clip-path="url(#clip0_1645_37)">
              <path d="M12 17H20C21.1046 17 22 16.1046 22 15V13M12 17H4C2.89543 17 2 16.1046 2 15V5C2 3.89543 2.89543 3 4 3H10M12 17V21M8 21H12M12 21H16M11.75 10.2917H13.2083L16.125 7.375H17.5833L20.5 4.45833H21.9583M16.125 11.75H17.5833L20.5 8.83333H21.9583M11.75 5.91667H13.2083L16.125 3H17.5833" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </g>
            <defs>
              <clipPath id="clip0_1645_37">
                <rect width="24" height="24" fill="white"/>
              </clipPath>
            </defs>
          </svg>
          <div class="sidebar-ad-text-container">
            <span class="sidebar-ad-text">Get started in minutes</span>
            <span class="sidebar-ad-text sidebar-ad-text-gradient">Download Langflow Desktop</span>
          </div>
        </a>
      `,
    },
  ],
};