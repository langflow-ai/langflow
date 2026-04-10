// ---------------------------------------------------------------------------
// Shared mock data for deployment E2E tests
// ---------------------------------------------------------------------------

export const PROVIDER = {
  id: "prov-1",
  name: "My Env",
  provider_key: "watsonx-orchestrate",
  url: "https://example.com",
  created_at: "2026-04-06T00:00:00Z",
};

export const PROVIDERS_MOCK = {
  provider_accounts: [PROVIDER],
  page: 1,
  size: 20,
  total: 1,
};

export const EMPTY_PROVIDERS_MOCK = { provider_accounts: [] };

export const NEW_PROVIDER = {
  id: "prov-new",
  name: "My Env",
  provider_key: "watsonx-orchestrate",
  url: "https://example.com",
  created_at: "2026-04-06T00:00:00Z",
};

export const DEPLOYMENT = {
  id: "dep-1",
  name: "Test Deployment",
  type: "agent",
  provider_account_id: "prov-1",
  provider_account_name: "My Env",
  status: "deployed",
};

export const DEPLOYMENTS_MOCK = { deployments: [DEPLOYMENT] };

export const DEPLOYMENT_DETAIL_MOCK = {
  ...DEPLOYMENT,
  provider_data: { llm: "ibm/granite-13b-chat" },
};

export const ATTACHMENTS_MOCK = {
  flow_versions: [
    {
      id: "fv1",
      flow_id: "f1",
      flow_name: "My Flow",
      version_number: 1,
      attached_at: "2026-04-06T00:00:00Z",
      provider_snapshot_id: null,
      tool_name: "my-flow",
      provider_data: null,
    },
  ],
  page: 1,
  size: 50,
  total: 1,
};

// Shape returned by GET /api/v1/deployments/llms — used in create stepper
export const LLMS_MOCK = {
  provider_data: {
    models: [{ model_name: "ibm/granite-13b-chat" }],
  },
};

export const CONFIGS_MOCK = {
  configs: [],
  page: 1,
  size: 10000,
  total: 0,
};

export const FLOWS_MOCK = [
  {
    id: "f1",
    name: "My Flow",
    is_component: false,
    folder_id: "my-collection",
    icon: "Workflow",
    description: "",
    data: null,
  },
];

export const FLOW_VERSIONS_MOCK = {
  entries: [
    {
      id: "fv1",
      flow_id: "f1",
      version_tag: "v1",
      version_number: 1,
      created_at: "2026-04-06T00:00:00Z",
      is_current: true,
    },
  ],
};

export const DEPLOY_RESPONSE = {
  id: "dep-new",
  name: "My Deployment",
  type: "agent",
  provider_account_id: "prov-1",
  status: "deploying",
};

// Attachments with provider_data for edit-mode connection tests.
// flow "f1" is already attached with connection "existing-app".
export const ATTACHMENTS_WITH_CONNECTIONS_MOCK = {
  flow_versions: [
    {
      id: "fv1",
      flow_id: "f1",
      flow_name: "My Flow",
      version_number: 1,
      attached_at: "2026-04-06T00:00:00Z",
      provider_snapshot_id: null,
      tool_name: "my-flow",
      provider_data: {
        tool_name: "my-flow",
        app_ids: ["existing-app"],
      },
    },
  ],
  page: 1,
  size: 50,
  total: 1,
};

// Configs (available connections) returned by the provider.
export const CONFIGS_WITH_CONNECTIONS_MOCK = {
  provider_data: {
    connections: [
      { connection_id: "conn-1", app_id: "existing-app" },
      { connection_id: "conn-2", app_id: "new-app" },
    ],
    page: 1,
    size: 10000,
    total: 2,
  },
};

export const POST_EXECUTION_RESPONSE = {
  deployment_id: "dep-1",
  provider_data: {
    execution_id: "exec-1",
    status: "running",
    thread_id: null,
    result: null,
  },
};

export const RUNNING_EXECUTION_RESPONSE = {
  deployment_id: "dep-1",
  provider_data: {
    execution_id: "exec-1",
    status: "running",
    result: null,
    thread_id: null,
  },
};

export const COMPLETED_EXECUTION_RESPONSE = {
  deployment_id: "dep-1",
  provider_data: {
    execution_id: "exec-1",
    status: "completed",
    thread_id: "thread-1",
    result: {
      data: {
        message: {
          content: [{ type: "text", text: "Hello from AI" }],
        },
      },
    },
  },
};
