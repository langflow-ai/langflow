// SVG icon helper for sidebar categories
const sidebarIcon = (svg, label) =>
  `<span class="sidebar-icon">${svg}</span><span>${label}</span>`;

const icons = {
  rocket: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>`,
  workflow: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/></svg>`,
  bot: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>`,
  plug: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a6 6 0 0 1-6 6v0a6 6 0 0 1-6-6V8z"/></svg>`,
  code: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`,
  cloud: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>`,
  blocks: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="14" y="3" rx="1"/><path d="M10 21V8a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5a1 1 0 0 0-1-1H3"/></svg>`,
  fileCode: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m10 13-2 2 2 2"/><path d="m14 17 2-2-2-2"/></svg>`,
  gitPR: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><path d="M6 9v12"/></svg>`,
  helpCircle: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>`,
};

module.exports = {
  docs: [
    // ── Build ───────────────────────────────
    {
      type: "html",
      value: `<div class="sidebar-group-label">Build</div>`,
      className: "sidebar-group-divider",
    },
    {
      type: "category",
      label: "Get started",
      className: "sidebar-category-with-icon sidebar-icon-rocket",
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
      label: "Flows",
      className: "sidebar-category-with-icon sidebar-icon-workflow",
      items: [
        {
          type: "doc",
          id: "Flows/concepts-overview",
          label: "Use the visual editor"
        },
        {
          type: "doc",
          id: "Flows/concepts-flows",
          label: "Build flows"
        },
        {
          type: "category",
          label: "Run flows",
          items: [
            {
              type: "doc",
              id: "Flows/concepts-publish",
              label: "Trigger flows with the Langflow API"
            },
            {
              type: "doc",
              id: "Flows/webhook",
              label: "Trigger flows with webhooks"
            },
          ],
        },
        {
          type: "doc",
          id: "Flows/concepts-playground",
          label: "Test flows"
        },
        {
          type: "doc",
          id: "Flows/concepts-flows-import",
          label: "Import and export flows"
        },
      ],
    },
    {
      type: "category",
      label: "Agents",
      className: "sidebar-category-with-icon sidebar-icon-bot",
      items: [
        "Agents/agents",
        "Agents/agents-tools",
      ],
    },
    {
      type: "category",
      label: "Model Context Protocol (MCP)",
      className: "sidebar-category-with-icon sidebar-icon-plug",
      items: [
        "Agents/mcp-client",
        "Agents/mcp-server",
        "Agents/mcp-component-astra",
      ],
    },
    // ── Develop & Deploy ──────────────────
    {
      type: "html",
      value: `<div class="sidebar-group-label">Develop & Deploy</div>`,
      className: "sidebar-group-divider",
    },
    {
      type: "category",
      label: "Develop",
      className: "sidebar-category-with-icon sidebar-icon-code",
      items: [
        "Develop/api-keys-and-authentication",
        "Develop/install-custom-dependencies",
        "Develop/configuration-global-variables",
        "Develop/environment-variables",
        {
          type: "category",
          label: "Storage and memory",
          items: [
            {
              type: "doc",
              id: "Develop/concepts-file-management",
              label: "Manage files"
            },
            {
              type: "doc",
              id: "Develop/memory",
              label: "Manage memory"
            },
            {
              type: "doc",
              id: "Develop/session-id",
              label: "Use Session IDs"
            },
            "Develop/configuration-custom-database",
            {
              type: "doc",
              id: "Develop/enterprise-database-guide",
              label: "Database guide for enterprise administrators"
            },
          ],
        },
        {
          type: "category",
          label: "Observability",
          items: [
            "Develop/logging",
            {
              type: "category",
              label: "Monitoring",
              items: [
                "Develop/integrations-arize",
                "Develop/integrations-langfuse",
                "Develop/integrations-langsmith",
                "Develop/integrations-langwatch",
                "Develop/integrations-opik",
                "Develop/integrations-instana-traceloop",
              ],
            },
            "Develop/contributing-telemetry",
          ],
        },
        {
          type: "doc",
          id: "Develop/data-types",
          label: "Use Langflow data types"
        },
        {
          type: "doc",
          id: "Develop/concepts-voice-mode",
          label: "Use voice mode"
        },
        {
          type: "doc",
          id: "Develop/configuration-cli",
          label: "Use the Langflow CLI"
        },
      ],
    },
    {
      type: "category",
      label: "Deploy",
      className: "sidebar-category-with-icon sidebar-icon-cloud",
      items: [
        {
          type:"doc",
          id: "Deployment/deployment-overview",
          label: "Langflow deployment overview"
        },
        {
          type: "doc",
          id: "Deployment/deployment-public-server",
          label: "Deploy a public Langflow server"
        },
        {
          type: "doc",
          id: "Deployment/deployment-nginx-ssl",
          label: "Deploy Langflow with Nginx and SSL"
        },
        {
          type: "category",
          label: "Containerized deployments",
          items: [
            "Deployment/develop-application",
            {
              type: "doc",
              id: "Deployment/deployment-docker",
              label: "Langflow Docker images"
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
                  id: "Deployment/deployment-architecture",
                  label: "Deployment architecture"
                },
                {
                  type: "doc",
                  id: "Deployment/deployment-prod-best-practices",
                  label: "Best practices"
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
                },
              ]
            },
          ],
        },
        {
          type: "category",
          label: "Cloud platforms",
          items: [
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
          ]
        },
        {
          type: "doc",
          id: "Deployment/security",
          label: "Security",
        },
      ],
    },
    // ── Reference ─────────────────────────
    {
      type: "html",
      value: `<div class="sidebar-group-label">Reference</div>`,
      className: "sidebar-group-divider",
    },
    {
      type: "category",
      label: "Components reference",
      className: "sidebar-category-with-icon sidebar-icon-blocks",
      items: [
        "Components/concepts-components",
        {
          type: "category",
          label: "Core components",
          items: [
            {
              type: "category",
              label: "Input / Output",
              items: [
                "Components/chat-input-and-output",
                "Components/text-input-and-output",
                "Components/webhook",
              ]
            },
            {
              type: "category",
              label: "Processing",
              items: [
                "Components/data-operations",
                "Components/dataframe-operations",
                "Components/dynamic-create-data",
                "Components/parser",
                "Components/split-text",
                "Components/type-convert",
              ]
            },
            {
              type: "category",
              label: "Data Source",
              items: [
                "Components/api-request",
                "Components/mock-data",
                "Components/url",
                "Components/web-search",
              ]
            },
            {
              type: "category",
              label: "Files",
              items: [
                "Components/directory",
                "Components/read-file",
                "Components/write-file",
              ]
            },
            {
              type: "category",
              label: "Flow Controls",
              items: [
                "Components/if-else",
                "Components/loop",
                "Components/notify-and-listen",
                "Components/run-flow",
              ]
            },
            {
              type: "category",
              label: "LLM Operations",
              items: [
                "Components/batch-run",
                "Components/llm-selector",
                "Components/smart-router",
                "Components/smart-transform",
                "Components/structured-output",
              ]
            },
            {
              type: "category",
              label: "Models and Agents",
              items: [
                "Components/components-models",
                "Components/components-prompts",
                "Components/components-agents",
                "Components/mcp-tools",
                "Components/components-embedding-models",
                "Components/message-history",
              ]
            },
            {
              type: "category",
              label: "Utilities",
              items: [
                "Components/calculator",
                "Components/current-date",
                "Components/python-interpreter",
                "Components/sql-database",
              ]
            },
            "Components/legacy-core-components",
          ],
        },
        {
          type: "category",
          label: "Bundles",
          items: [
            "Components/components-bundles",
            "Components/bundles-aiml",
            "Components/bundles-altk",
            "Components/bundles-amazon",
            "Components/bundles-anthropic",
            "Components/bundles-apify",
            "Components/bundles-arxiv",
            "Components/bundles-assemblyai",
            "Components/bundles-azure",
            "Components/bundles-baidu",
            "Components/bundles-bing",
            "Components/bundles-cassandra",
            "Components/bundles-chroma",
            "Components/bundles-cleanlab",
            "Components/bundles-clickhouse",
            "Components/bundles-cloudflare",
            "Components/bundles-cohere",
            "Components/bundles-cometapi",
            "Components/bundles-composio",
            "Components/bundles-couchbase",
            "Components/bundles-cuga",
            "Components/bundles-datastax",
            "Components/bundles-deepseek",
            "Components/bundles-docling",
            "Components/bundles-duckduckgo",
            "Components/bundles-elastic",
            "Components/bundles-exa",
            "Components/bundles-faiss",
            "Components/bundles-glean",
            "Components/bundles-google",
            "Components/bundles-groq",
            "Components/bundles-huggingface",
            "Components/bundles-ibm",
            "Components/bundles-icosacomputing",
            "Components/bundles-langchain",
            "Components/bundles-lmstudio",
            "Components/bundles-maritalk",
            "Components/bundles-mem0",
            "Components/bundles-milvus",
            "Components/bundles-mistralai",
            "Components/bundles-mongodb",
            "Components/bundles-notion",
            "Components/bundles-novita",
            "Components/bundles-nvidia",
            "Components/bundles-ollama",
            "Components/bundles-openai",
            "Components/bundles-openrouter",
            "Components/bundles-perplexity",
            "Components/bundles-pgvector",
            "Components/bundles-pinecone",
            "Components/bundles-qdrant",
            "Components/bundles-redis",
            "Components/bundles-sambanova",
            "Components/bundles-searchapi",
            "Components/bundles-serper",
            "Components/bundles-supabase",
            "Components/bundles-upstash",
            "Components/bundles-vllm",
            "Components/bundles-vectara",
            "Components/bundles-vertexai",
            "Components/bundles-weaviate",
            "Components/bundles-wikipedia",
            "Components/bundles-xai",
          ],
        },
        "Components/components-custom-components",
      ],
    },
    {
      type: "category",
      label: "API reference",
      className: "sidebar-category-with-icon sidebar-icon-fileCode",
      items: [
        {
          type: "doc",
          id: "API-Reference/api-reference-api-examples",
          label: "Get started with the Langflow API",
        },
        {
          type: "doc",
          id: "API-Reference/typescript-client",
          label: "Use the TypeScript client"
        },
        {
          type: "doc",
          id: "API-Reference/api-flows-run",
          label: "Flow trigger endpoints",
        },
        {
          type: "doc",
          id: "API-Reference/api-openai-responses",
          label: "OpenAI Responses endpoints",
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
    // ── Community ─────────────────────────
    {
      type: "html",
      value: `<div class="sidebar-group-label">Community</div>`,
      className: "sidebar-group-divider",
    },
    {
      type: "category",
      label: "Contribute",
      className: "sidebar-category-with-icon sidebar-icon-gitPR",
      items: [
        "Contributing/contributing-community",
        "Contributing/contributing-how-to-contribute",
        "Contributing/contributing-components",
        "Contributing/contributing-bundles",
        "Contributing/contributing-component-tests",
        "Contributing/contributing-templates",
      ],
    },
    {
      type: "category",
      label: "Support",
      className: "sidebar-category-with-icon sidebar-icon-helpCircle",
      items: [
        {
          type: "doc",
          id: "Support/troubleshooting",
          label: "Troubleshoot",
        },
        {
          type: "doc",
          id: "Support/contributing-github-issues",
          label: "Get help and request enhancements",
        },
        {
          type: "doc",
          id: "Support/luna-for-langflow",
          label: "IBM Elite Support for Langflow",
        },
        {
          type: "doc",
          id: "Support/release-notes",
          label: "Release notes",
        },
      ],
    },
  ],
};
