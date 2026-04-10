import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import type {
  ConnectionItem,
  DeploymentProvider,
  ProviderAccount,
} from "../types";

jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({ usePostProviderAccount: jest.fn() }),
);
jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: jest.fn(),
}));
jest.mock("@/controllers/API/queries/deployments/use-patch-deployment", () => ({
  usePatchDeployment: jest.fn(),
}));

const mockProvider: DeploymentProvider = {
  id: "provider-1",
  type: "watsonx",
  name: "watsonx Orchestrate",
  icon: "watsonx-icon",
};

const mockInstance: ProviderAccount = {
  id: "instance-1",
  name: "My WxO Instance",
  provider_key: "watsonx-orchestrate",
  url: "https://api.example.com",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

function renderCreateHook(
  initialState?: Parameters<
    typeof DeploymentStepperProvider
  >[0]["initialState"],
) {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <DeploymentStepperProvider initialState={initialState}>
      {children}
    </DeploymentStepperProvider>
  );
  return renderHook(() => useDeploymentStepper(), { wrapper });
}

// ---------------------------------------------------------------------------
// Create mode — basic state
// ---------------------------------------------------------------------------

describe("Create mode — basic state", () => {
  it("starts in create mode with 4 steps", () => {
    const { result } = renderCreateHook();
    expect(result.current.isEditMode).toBe(false);
    expect(result.current.totalSteps).toBe(4);
    expect(result.current.currentStep).toBe(1);
    expect(result.current.editingDeployment).toBeNull();
  });

  it("defaults to agent type with empty fields", () => {
    const { result } = renderCreateHook();
    expect(result.current.deploymentType).toBe("agent");
    expect(result.current.deploymentName).toBe("");
    expect(result.current.deploymentDescription).toBe("");
    expect(result.current.selectedLlm).toBe("");
  });

  it("starts with empty flow/connection maps", () => {
    const { result } = renderCreateHook();
    expect(result.current.selectedVersionByFlow.size).toBe(0);
    expect(result.current.attachedConnectionByFlow.size).toBe(0);
    expect(result.current.toolNameByFlow.size).toBe(0);
    expect(result.current.connections).toEqual([]);
  });

  it("starts with no provider/instance selected", () => {
    const { result } = renderCreateHook();
    expect(result.current.selectedProvider).toBeNull();
    expect(result.current.selectedInstance).toBeNull();
  });

  it("accepts initialProvider and initialInstance", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });
    expect(result.current.selectedProvider).toEqual(mockProvider);
    expect(result.current.selectedInstance).toEqual(mockInstance);
  });

  it("accepts initialFlowId", () => {
    const { result } = renderCreateHook({ initialFlowId: "flow-abc" });
    expect(result.current.initialFlowId).toBe("flow-abc");
  });
});

// ---------------------------------------------------------------------------
// Create mode — canGoNext validation per step
// ---------------------------------------------------------------------------

describe("Create mode — canGoNext validation", () => {
  describe("Step 1 (Provider)", () => {
    it("blocks when no provider selected", () => {
      const { result } = renderCreateHook();
      expect(result.current.canGoNext).toBe(false);
    });

    it("blocks when provider selected but no instance or credentials", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
      });
      expect(result.current.canGoNext).toBe(false);
    });

    it("allows when provider + existing instance selected", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });
      expect(result.current.canGoNext).toBe(true);
    });

    it("allows when provider + valid credentials entered", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
      });

      act(() => {
        result.current.setCredentials({
          name: "New Account",
          provider_key: "watsonx-orchestrate",
          url: "https://api.example.com",
          api_key: "my-secret-key", // pragma: allowlist secret
        });
      });

      expect(result.current.canGoNext).toBe(true);
    });

    it("blocks when credentials are partially filled", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
      });

      act(() => {
        result.current.setCredentials({
          name: "New Account",
          provider_key: "watsonx-orchestrate",
          url: "",
          api_key: "my-secret-key", // pragma: allowlist secret
        });
      });

      expect(result.current.canGoNext).toBe(false);
    });
  });

  describe("Step 2 (Type)", () => {
    it("blocks when name is empty", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2
      expect(result.current.currentStep).toBe(2);

      act(() => result.current.setSelectedLlm("gpt-4"));
      expect(result.current.canGoNext).toBe(false);
    });

    it("blocks when LLM is empty", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2

      act(() => result.current.setDeploymentName("My Agent"));
      expect(result.current.canGoNext).toBe(false);
    });

    it("blocks when name is whitespace-only", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2

      act(() => {
        result.current.setDeploymentName("   ");
        result.current.setSelectedLlm("gpt-4");
      });

      expect(result.current.canGoNext).toBe(false);
    });

    it("allows when both name and LLM are set", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2

      act(() => {
        result.current.setDeploymentName("My Agent");
        result.current.setSelectedLlm("gpt-4");
      });

      expect(result.current.canGoNext).toBe(true);
    });
  });

  describe("Step 3 (Attach Flows)", () => {
    it("blocks when no flows attached in create mode", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      // Navigate to step 3
      act(() => result.current.handleNext()); // → step 2
      act(() => {
        result.current.setDeploymentName("My Agent");
        result.current.setSelectedLlm("gpt-4");
      });
      act(() => result.current.handleNext()); // → step 3

      expect(result.current.currentStep).toBe(3);
      expect(result.current.canGoNext).toBe(false);
    });

    it("allows when at least one flow is attached", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2
      act(() => {
        result.current.setDeploymentName("My Agent");
        result.current.setSelectedLlm("gpt-4");
      });
      act(() => result.current.handleNext()); // → step 3

      act(() => {
        result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      });

      expect(result.current.canGoNext).toBe(true);
    });
  });

  describe("Step 4 (Review)", () => {
    it("always allows proceeding (review is the final step)", () => {
      const { result } = renderCreateHook({
        initialProvider: mockProvider,
        initialInstance: mockInstance,
      });

      act(() => result.current.handleNext()); // → step 2
      act(() => {
        result.current.setDeploymentName("My Agent");
        result.current.setSelectedLlm("gpt-4");
      });
      act(() => result.current.handleNext()); // → step 3
      act(() => {
        result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      });
      act(() => result.current.handleNext()); // → step 4

      expect(result.current.currentStep).toBe(4);
      expect(result.current.canGoNext).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------
// Create mode — step navigation
// ---------------------------------------------------------------------------

describe("Create mode — step navigation", () => {
  it("handleNext increments step", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });

    act(() => result.current.handleNext());
    expect(result.current.currentStep).toBe(2);
  });

  it("handleBack decrements step", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });

    act(() => result.current.handleNext());
    act(() => result.current.handleBack());
    expect(result.current.currentStep).toBe(1);
  });

  it("handleBack does not go below minStep", () => {
    const { result } = renderCreateHook();
    act(() => result.current.handleBack());
    expect(result.current.currentStep).toBe(1);
  });

  it("handleNext does not exceed totalSteps", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });

    // Navigate all the way to step 4
    act(() => result.current.handleNext());
    act(() => result.current.handleNext());
    act(() => result.current.handleNext());
    act(() => result.current.handleNext()); // should stay at 4

    expect(result.current.currentStep).toBe(4);
  });

  it("respects initialStep", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
      initialStep: 2,
    });

    expect(result.current.currentStep).toBe(2);
    expect(result.current.minStep).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Create mode — provider selection
// ---------------------------------------------------------------------------

describe("Create mode — provider selection", () => {
  it("setSelectedProvider clears instance and credentials", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });

    const newProvider: DeploymentProvider = {
      id: "provider-2",
      type: "kubernetes",
      name: "Kubernetes",
      icon: "k8s-icon",
    };

    act(() => result.current.setSelectedProvider(newProvider));

    expect(result.current.selectedProvider).toEqual(newProvider);
    expect(result.current.selectedInstance).toBeNull();
    expect(result.current.credentials).toEqual({
      name: "",
      provider_key: "",
      url: "",
      api_key: "",
    });
  });

  it("needsProviderAccountCreation is true when no instance but valid credentials", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
    });

    act(() => {
      result.current.setCredentials({
        name: "New Account",
        provider_key: "watsonx-orchestrate",
        url: "https://api.example.com",
        api_key: "my-secret-key", // pragma: allowlist secret
      });
    });

    expect(result.current.needsProviderAccountCreation).toBe(true);
  });

  it("needsProviderAccountCreation is false when instance is selected", () => {
    const { result } = renderCreateHook({
      initialProvider: mockProvider,
      initialInstance: mockInstance,
    });

    expect(result.current.needsProviderAccountCreation).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Create mode — flow version selection
// ---------------------------------------------------------------------------

describe("Create mode — flow version selection", () => {
  it("handleSelectVersion adds a new flow-version mapping", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    expect(result.current.selectedVersionByFlow.size).toBe(1);
    expect(result.current.selectedVersionByFlow.get("flow-1")).toEqual({
      versionId: "ver-1",
      versionTag: "v1",
    });
  });

  it("handleSelectVersion overwrites existing version for same flow", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });
    act(() => {
      result.current.handleSelectVersion("flow-1", "ver-2", "v2");
    });

    expect(result.current.selectedVersionByFlow.size).toBe(1);
    expect(result.current.selectedVersionByFlow.get("flow-1")).toEqual({
      versionId: "ver-2",
      versionTag: "v2",
    });
  });

  it("handles multiple flows independently", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
      result.current.handleSelectVersion("flow-3", "ver-3", "v3");
    });

    expect(result.current.selectedVersionByFlow.size).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// Create mode — connection management
// ---------------------------------------------------------------------------

describe("Create mode — connection management", () => {
  it("setConnections stores connection items", () => {
    const { result } = renderCreateHook();

    const conns: ConnectionItem[] = [
      {
        id: "conn-1",
        name: "DB Connection",
        variableCount: 2,
        isNew: true,
        environmentVariables: { DB_HOST: "localhost", DB_PORT: "5432" },
      },
    ];

    act(() => result.current.setConnections(conns));
    expect(result.current.connections).toEqual(conns);
  });

  it("setAttachedConnectionByFlow maps flows to connections", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-1", ["conn-1", "conn-2"]],
          ["flow-2", ["conn-3"]],
        ]),
      );
    });

    expect(result.current.attachedConnectionByFlow.get("flow-1")).toEqual([
      "conn-1",
      "conn-2",
    ]);
    expect(result.current.attachedConnectionByFlow.get("flow-2")).toEqual([
      "conn-3",
    ]);
  });
});

// ---------------------------------------------------------------------------
// Create mode — buildProviderAccountPayload
// ---------------------------------------------------------------------------

describe("Create mode — buildProviderAccountPayload", () => {
  it("returns null when credentials are not valid", () => {
    const { result } = renderCreateHook();
    expect(result.current.buildProviderAccountPayload()).toBeNull();
  });

  it("returns null when credentials are partially filled", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "Account",
        provider_key: "watsonx-orchestrate",
        url: "",
        api_key: "key-123", // pragma: allowlist secret
      });
    });

    expect(result.current.buildProviderAccountPayload()).toBeNull();
  });

  it("returns correct payload shape when credentials are valid", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "  My Account  ",
        provider_key: "watsonx-orchestrate",
        url: "  https://api.example.com  ",
        api_key: "  secret-key-123  ", // pragma: allowlist secret
      });
    });

    const payload = result.current.buildProviderAccountPayload();
    expect(payload).toEqual({
      name: "My Account",
      provider_key: "watsonx-orchestrate",
      provider_data: {
        url: "https://api.example.com",
        api_key: "secret-key-123", // pragma: allowlist secret
      },
    });
  });

  it("trims whitespace from all credential fields", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "  padded  ",
        provider_key: "watsonx-orchestrate",
        url: "  https://padded.com  ",
        api_key: "  padded-key  ", // pragma: allowlist secret
      });
    });

    const payload = result.current.buildProviderAccountPayload();
    expect(payload).toBeDefined();
    if (!payload) return;
    expect(payload.name).toBe("padded");
    expect(payload.provider_data.url).toBe("https://padded.com");
    expect(payload.provider_data.api_key).toBe("padded-key"); // pragma: allowlist secret
  });
});

// ---------------------------------------------------------------------------
// Create mode — buildDeploymentPayload
// ---------------------------------------------------------------------------

describe("Create mode — buildDeploymentPayload", () => {
  it("builds correct spec with name, description, and type", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setDeploymentDescription("Agent description");
      result.current.setDeploymentType("agent");
      result.current.setSelectedLlm("gpt-4");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    expect(payload.provider_id).toBe("provider-1");
    expect(payload.name).toBe("Test Agent");
    expect(payload.description).toBe("Agent description");
    expect(payload.type).toBe("agent");
  });

  it("includes LLM in provider_data", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("granite-3b");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.llm).toBe("granite-3b");
  });

  it("builds add_flows entries for each attached flow", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.add_flows).toHaveLength(2);
    expect(payload.provider_data.add_flows[0].flow_version_id).toBeDefined();
    expect(payload.provider_data.add_flows[1].flow_version_id).toBeDefined();
  });

  it("includes app_ids from attachedConnectionByFlow", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["app-1", "app-2"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const addFlow = payload.provider_data.add_flows[0];
    expect(addFlow.app_ids).toEqual(["app-1", "app-2"]);
  });

  it("includes raw_payloads only for new connections", () => {
    const { result } = renderCreateHook();

    const newConn: ConnectionItem = {
      id: "conn-new",
      name: "New Connection",
      variableCount: 1,
      isNew: true,
      environmentVariables: { API_URL: "https://example.com" },
    };
    const existingConn: ConnectionItem = {
      id: "conn-existing",
      name: "Existing Connection",
      variableCount: 0,
      isNew: false,
      environmentVariables: {},
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setConnections([newConn, existingConn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-new", "conn-existing"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const connections = payload.provider_data.connections;
    expect(connections).toHaveLength(1);
    expect(connections[0].app_id).toBe("conn-new");
  });

  it("wraps env vars with source: raw by default", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      name: "Connection",
      variableCount: 1,
      isNew: true,
      environmentVariables: { DB_HOST: "localhost" },
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;
    const dbHostCred = credentials.find((c) => c.key === "DB_HOST");
    expect(dbHostCred).toEqual({
      key: "DB_HOST",
      value: "localhost",
      source: "raw",
    });
  });

  it("wraps global var keys with source: variable", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      name: "Connection",
      variableCount: 2,
      isNew: true,
      environmentVariables: {
        DB_HOST: "localhost",
        SECRET_KEY: "my-global-var", // pragma: allowlist secret
      },
      globalVarKeys: new Set(["SECRET_KEY"]),
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;
    const dbHostCred = credentials.find((c) => c.key === "DB_HOST");
    const secretKeyCred = credentials.find((c) => c.key === "SECRET_KEY");
    expect(dbHostCred).toEqual({
      key: "DB_HOST",
      value: "localhost",
      source: "raw",
    });
    expect(secretKeyCred).toEqual({
      key: "SECRET_KEY",
      value: "my-global-var",
      source: "variable",
    });
  });

  it("returns empty raw_payloads when no new connections", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.connections).toEqual([]);
  });

  it("returns empty add_flows when no flows attached", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.add_flows).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Create mode — multi-flow scenarios
// ---------------------------------------------------------------------------

describe("Create mode — multi-flow scenarios", () => {
  it("builds payload with 3+ flows, connections, and tool names", () => {
    const { result } = renderCreateHook();

    const conn1: ConnectionItem = {
      id: "conn-a",
      name: "Connection A",
      variableCount: 1,
      isNew: true,
      environmentVariables: { KEY_A: "val-a" },
    };
    const conn2: ConnectionItem = {
      id: "conn-b",
      name: "Connection B",
      variableCount: 1,
      isNew: true,
      environmentVariables: { KEY_B: "val-b" },
    };

    act(() => {
      result.current.setDeploymentName("Multi-Flow Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
      result.current.handleSelectVersion("flow-3", "ver-3", "v3");
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "Tool Alpha"],
          ["flow-2", "Tool Beta"],
          // flow-3 intentionally has no custom name
        ]),
      );
      result.current.setConnections([conn1, conn2]);
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-1", ["conn-a"]],
          ["flow-2", ["conn-b"]],
          ["flow-3", ["conn-a", "conn-b"]],
        ]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const addFlows = payload.provider_data.add_flows;

    expect(addFlows).toHaveLength(3);

    const flow1Op = addFlows.find((o) => o.flow_version_id === "ver-1");
    expect(flow1Op?.tool_name).toBe("Tool Alpha");
    expect(flow1Op?.app_ids).toEqual(["conn-a"]);

    const flow2Op = addFlows.find((o) => o.flow_version_id === "ver-2");
    expect(flow2Op?.tool_name).toBe("Tool Beta");
    expect(flow2Op?.app_ids).toEqual(["conn-b"]);

    const flow3Op = addFlows.find((o) => o.flow_version_id === "ver-3");
    expect(flow3Op?.tool_name).toBeUndefined();
    expect(flow3Op?.app_ids).toEqual(["conn-a", "conn-b"]);

    // Both connections are new, so both appear in connections
    const connections = payload.provider_data.connections;
    expect(connections).toHaveLength(2);
    const appIds = connections.map((r) => r.app_id).sort();
    expect(appIds).toEqual(["conn-a", "conn-b"]);
  });

  it("deduplicates connections in raw_payloads across flows", () => {
    const { result } = renderCreateHook();

    const sharedConn: ConnectionItem = {
      id: "conn-shared",
      name: "Shared Connection",
      variableCount: 1,
      isNew: true,
      environmentVariables: { SHARED_KEY: "shared-val" },
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
      result.current.setConnections([sharedConn]);
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-1", ["conn-shared"]],
          ["flow-2", ["conn-shared"]],
        ]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    // Even though both flows reference the same connection, it should only appear once
    expect(payload.provider_data.connections).toHaveLength(1);
    expect(payload.provider_data.connections[0].app_id).toBe("conn-shared");
  });
});

// ---------------------------------------------------------------------------
// Create mode — edge cases
// ---------------------------------------------------------------------------

describe("Create mode — edge cases", () => {
  it("empty description is allowed in payload", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.description).toBe("");
  });

  it("buildDeploymentPayload works with MCP deployment type", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("MCP Server");
      result.current.setDeploymentType("mcp");
      result.current.setSelectedLlm("model-1");
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.type).toBe("mcp");
  });

  it("connection with empty environmentVariables produces empty object", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-empty",
      name: "Empty Vars",
      variableCount: 0,
      isNew: true,
      environmentVariables: {},
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-empty"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.connections[0].credentials).toEqual([]);
  });

  it("buildDeploymentUpdatePayload throws in create mode", () => {
    const { result } = renderCreateHook();
    expect(() => result.current.buildDeploymentUpdatePayload()).toThrow(
      "buildDeploymentUpdatePayload called outside edit mode",
    );
  });
});
