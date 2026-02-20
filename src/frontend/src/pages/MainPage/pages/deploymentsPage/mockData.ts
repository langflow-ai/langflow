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
