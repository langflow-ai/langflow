export const MOCK_DEPLOYMENTS = [
  {
    name: "Production Sales Agent",
    url: "https://api.production.example.com/sales-agent",
    type: "Agent",
    status: "Healthy",
    attached: 2,
    configs: [{ id: "SALES_BOT_PROD", count: 3 }],
    modifiedDate: "2026-02-15",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Test Environment Sales Agent",
    url: "https://api.staging.example.com/sales-agent",
    type: "Agent",
    status: "Healthy",
    attached: 1,
    configs: [{ id: "SALES_BOT_STAGING", count: 2 }],
    modifiedDate: "2026-02-18",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Customer Support MCP",
    url: "https://api.dev.example.com/customer-support",
    type: "MCP",
    status: "Pending",
    attached: 1,
    configs: [{ id: "CUSTOMER_SUPPORT_PROD", count: null }],
    modifiedDate: "2026-02-19",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Multi-Config Sales Pipeline",
    url: "https://api.dev.example.com/multi-config",
    type: "Agent",
    status: "Unhealthy",
    attached: 3,
    configs: [
      { id: "SALES_BOT_PROD", count: 3 },
      { id: "SALES_BOT_STAGING", count: 2 },
    ],
    modifiedDate: "2026-02-08",
    modifiedBy: "Sarah Han",
  },
];

export const MOCK_FLOWS = [
  {
    id: "flow-1",
    name: "Qualify Lead",
    updatedDate: "2026-02-18",
    snapshotDate: "2026-02-17",
  },
  {
    id: "flow-2",
    name: "Summarize Call Notes",
    updatedDate: "2026-02-19",
    snapshotDate: "2026-02-18",
  },
  {
    id: "flow-3",
    name: "Create Ticket",
    updatedDate: "2026-02-16",
    snapshotDate: null,
  },
];

export const MOCK_SNAPSHOTS = [
  { id: "snap-1", name: "Qualify Lead v1.2", updatedDate: "2026-02-17" },
  {
    id: "snap-2",
    name: "Summarize Call Notes v2.0",
    updatedDate: "2026-02-18",
  },
];

export const MOCK_PROVIDERS = [
  {
    id: "langflow-cloud",
    name: "Langflow Cloud",
    subLabel: "Langflow",
    icon: "LangflowLogo",
    iconBg: "bg-zinc-700",
    iconColor: "text-white",
    status: "Connected",
    endpoint: "https://cloud.langflow.io",
    lastVerified: "6 days ago",
    deployments: 12,
  },
  {
    id: "watsonx",
    name: "watsonx Orchestrate",
    subLabel: "watsonx",
    icon: "WatsonxAI",
    iconBg: "bg-blue-600",
    iconColor: "text-white",
    status: "Connected",
    endpoint: "https://api.watsonx-orchestrate.ibm.com/inst",
    lastVerified: "6 days ago",
    deployments: 8,
  },
  {
    id: "aws",
    name: "AWS Cloud Deploy",
    subLabel: "cloud",
    icon: "AWS",
    iconBg: "bg-[#232F3E]",
    iconColor: "text-[#FF9900]",
    status: "Error",
    endpoint: "https://aws.example.com",
    lastVerified: "6 days ago",
    deployments: 3,
  },
  {
    id: "azure",
    name: "Azure Functions",
    subLabel: "cloud",
    icon: "Azure",
    iconBg: "bg-[#0078D4]",
    iconColor: "text-white",
    status: "Connected",
    endpoint: "https://azure-functions.microsoft.com",
    lastVerified: "6 days ago",
    deployments: 5,
  },
];

export const MOCK_CONFIGURATIONS = [
  {
    id: "config-1",
    name: "Standard Production Config",
    description: "Default configuration for production environments",
    usedBy: 15,
    created: "Jan 14, 2026",
  },
  {
    id: "config-2",
    name: "Test Environment Config",
    description: "Lightweight configuration for testing environments",
    usedBy: 8,
    created: "Jan 19, 2026",
  },
  {
    id: "config-3",
    name: "High Performance Config",
    description: "Enhanced configuration for high-load scenarios",
    usedBy: 3,
    created: "Jan 31, 2026",
  },
];
