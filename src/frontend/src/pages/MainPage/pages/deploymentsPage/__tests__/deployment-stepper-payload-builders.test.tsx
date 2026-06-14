import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import type { ConnectionItem, Deployment } from "../types";

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

const mockDeployment: Deployment = {
  id: "deploy-1",
  provider_id: "prov-1",
  provider_data: { display_name: "My Agent", name: "my_agent" },
  description: "A test agent",
  type: "agent",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  resource_key: "my-agent-key",
  attached_count: 2,
};

function renderEditHook(
  overrides?: Partial<{
    editingDeployment: Deployment;
    selectedVersionByFlow: Map<
      string,
      { versionId: string; versionTag: string }
    >;
    initialLlm: string;
    initialToolNameByFlow: Map<string, string>;
    initialConnectionsByFlow: Map<string, string[]>;
  }>,
) {
  const defaults = {
    editingDeployment: mockDeployment,
    selectedVersionByFlow: new Map([
      ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
      ["flow-2", { versionId: "ver-2", versionTag: "v2" }],
    ]),
    initialLlm: "test-model",
    initialToolNameByFlow: new Map([
      ["flow-1", "tool_one"],
      ["flow-2", "tool_two"],
    ]),
    initialConnectionsByFlow: new Map([
      ["flow-1", ["app-1"]],
      ["flow-2", ["app-2"]],
    ]),
  };
  const merged = { ...defaults, ...overrides };
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <DeploymentStepperProvider initialState={merged}>
      {children}
    </DeploymentStepperProvider>
  );
  return renderHook(() => useDeploymentStepper(), { wrapper });
}

// ---------------------------------------------------------------------------
// buildConnectionPayloads (tested through buildDeploymentPayload)
// ---------------------------------------------------------------------------

describe("buildConnectionPayloads", () => {
  it("filters to only isNew connections", () => {
    const { result } = renderCreateHook();

    const newConn: ConnectionItem = {
      id: "conn-new",
      connectionId: "cid-new",
      name: "New",
      variableCount: 1,
      isNew: true,
      environmentVariables: { KEY: "val" },
    };
    const existingConn: ConnectionItem = {
      id: "conn-existing",
      connectionId: "cid-existing",
      name: "Existing",
      variableCount: 1,
      isNew: false,
      environmentVariables: { KEY2: "val2" },
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
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

  it("maps environmentVariables to credentials array", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      connectionId: "cid-1",
      name: "Connection",
      variableCount: 3,
      isNew: true,
      environmentVariables: {
        DB_HOST: "localhost",
        DB_PORT: "5432",
        DB_NAME: "mydb",
      },
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;
    expect(credentials).toHaveLength(3);

    const keys = credentials.map((c) => c.key).sort();
    expect(keys).toEqual(["DB_HOST", "DB_NAME", "DB_PORT"]);
  });

  it("identifies 'variable' source type for globalVarKeys entries", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      connectionId: "cid-1",
      name: "Connection",
      variableCount: 2,
      isNew: true,
      environmentVariables: {
        PUBLIC_URL: "https://example.com",
        SECRET_TOKEN: "my-global-var", // pragma: allowlist secret
      },
      globalVarKeys: new Set(["SECRET_TOKEN"]),
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;

    const secretCred = credentials.find((c) => c.key === "SECRET_TOKEN");
    expect(secretCred).toEqual({
      key: "SECRET_TOKEN",
      value: "my-global-var",
      source: "variable",
    });
  });

  it("identifies 'raw' source type for non-globalVar entries", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      connectionId: "cid-1",
      name: "Connection",
      variableCount: 2,
      isNew: true,
      environmentVariables: {
        PUBLIC_URL: "https://example.com",
        SECRET_TOKEN: "my-global-var", // pragma: allowlist secret
      },
      globalVarKeys: new Set(["SECRET_TOKEN"]),
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;

    const publicCred = credentials.find((c) => c.key === "PUBLIC_URL");
    expect(publicCred).toEqual({
      key: "PUBLIC_URL",
      value: "https://example.com",
      source: "raw",
    });
  });

  it("handles empty environmentVariables", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-empty",
      connectionId: "cid-empty",
      name: "Empty",
      variableCount: 0,
      isNew: true,
      environmentVariables: {},
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-empty"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.connections[0].credentials).toEqual([]);
  });

  it("handles connection with no globalVarKeys (all raw)", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      connectionId: "cid-1",
      name: "All Raw",
      variableCount: 2,
      isNew: true,
      environmentVariables: {
        HOST: "localhost",
        PORT: "8080",
      },
      // no globalVarKeys
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;
    expect(credentials).toHaveLength(2);
    expect(credentials.every((c) => c.source === "raw")).toBe(true);
  });

  it("handles connection with all globalVarKeys (all variable)", () => {
    const { result } = renderCreateHook();

    const conn: ConnectionItem = {
      id: "conn-1",
      connectionId: "cid-1",
      name: "All Variable",
      variableCount: 2,
      isNew: true,
      environmentVariables: {
        SECRET_A: "var-a", // pragma: allowlist secret
        SECRET_B: "var-b", // pragma: allowlist secret
      },
      globalVarKeys: new Set(["SECRET_A", "SECRET_B"]),
    };

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setConnections([conn]);
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const credentials = payload.provider_data.connections[0].credentials;
    expect(credentials).toHaveLength(2);
    expect(credentials.every((c) => c.source === "variable")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// buildDeploymentUpdatePayload
// ---------------------------------------------------------------------------

describe("buildDeploymentUpdatePayload", () => {
  it("detects unchanged pre-existing flows and skips them", () => {
    const { result } = renderEditHook();

    // No changes to any flows — neither tool names nor connections modified
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(upsertFlows).toHaveLength(0);
    expect(removeFlows).toHaveLength(0);
  });

  it("calculates add_flows correctly for new flows", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new-a",
        flowName: "Flow",
        versionId: "ver-new-a",
        versionTag: "v1",
      });
      result.current.handleSelectVersion({
        flowId: "flow-new-b",
        flowName: "Flow",
        versionId: "ver-new-b",
        versionTag: "v1",
      });
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-1", ["app-1"]], // unchanged
          ["flow-2", ["app-2"]], // unchanged
          ["flow-new-a", ["app-10"]],
          ["flow-new-b", []],
        ]),
      );
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "tool_one"],
          ["flow-2", "tool_two"],
          ["flow-new-a", "New Tool A"],
        ]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as {
          upsert_flows?: Array<{
            flow_version_id: string;
            add_app_ids: string[];
            remove_app_ids: string[];
            tool_display_name?: string;
          }>;
        }
      )?.upsert_flows ?? [];

    // Only the two new flows should appear
    expect(upsertFlows).toHaveLength(2);

    const flowA = upsertFlows.find((f) => f.flow_version_id === "ver-new-a");
    expect(flowA).toBeDefined();
    expect(flowA!.add_app_ids).toEqual(["app-10"]);
    expect(flowA!.tool_display_name).toBe("New Tool A");

    const flowB = upsertFlows.find((f) => f.flow_version_id === "ver-new-b");
    expect(flowB).toBeDefined();
    expect(flowB!.add_app_ids).toEqual([]);
    expect(flowB!.tool_display_name).toBe("Flow");
  });

  it("omits description when no changes detected", () => {
    const { result } = renderEditHook({ initialLlm: "" });
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload).toEqual({ deployment_id: "deploy-1" });
  });

  it("detects empty update payloads", async () => {
    const { isDeploymentUpdatePayloadEmpty } = await import(
      "../helpers/deployment-payload-builders"
    );
    expect(isDeploymentUpdatePayloadEmpty({ deployment_id: "deploy-1" })).toBe(
      true,
    );
    expect(
      isDeploymentUpdatePayloadEmpty({
        deployment_id: "deploy-1",
        description: "updated",
      }),
    ).toBe(false);
  });

  it("includes description change when description differs from initial", () => {
    const { result } = renderEditHook();

    act(() => result.current.setDeploymentDescription("Brand new description"));

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.description).toBe("Brand new description");
  });

  it("omits description when description is unchanged", () => {
    const { result } = renderEditHook();

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data).toBeUndefined();
    expect(payload.description).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// buildDeploymentPayload (create mode)
// ---------------------------------------------------------------------------

describe("buildDeploymentPayload", () => {
  it("includes provider_id, display name, type, description, connections", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setDeploymentDescription("A test description");
      result.current.setDeploymentType("agent");
      result.current.setSelectedLlm("gpt-4");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
    });

    const payload = result.current.buildDeploymentPayload("provider-abc");
    expect(payload.provider_id).toBe("provider-abc");
    expect(payload.type).toBe("agent");
    expect(payload.description).toBe("A test description");
    expect(payload.provider_data).toBeDefined();
    expect(payload.provider_data.display_name).toBe("Test Agent");
    expect(payload.provider_data.connections).toBeDefined();
    expect(payload.provider_data.add_flows).toBeDefined();
    expect(payload.provider_data.llm).toBe("gpt-4");
  });

  it("includes add_flows with correct version IDs and tool names", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-a",
        flowName: "Flow",
        versionId: "ver-a",
        versionTag: "v1",
      });
      result.current.handleSelectVersion({
        flowId: "flow-b",
        flowName: "Flow",
        versionId: "ver-b",
        versionTag: "v2",
      });
      result.current.setToolNameByFlow(
        new Map([
          ["flow-a", "Alpha Tool"],
          ["flow-b", "Beta Tool"],
        ]),
      );
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-a", ["conn-1"]],
          ["flow-b", ["conn-2", "conn-3"]],
        ]),
      );
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    const addFlows = payload.provider_data.add_flows;
    expect(addFlows).toHaveLength(2);

    const flowA = addFlows.find((f) => f.flow_version_id === "ver-a");
    expect(flowA).toBeDefined();
    expect(flowA!.tool_display_name).toBe("Alpha Tool");
    expect(flowA!.app_ids).toEqual(["conn-1"]);

    const flowB = addFlows.find((f) => f.flow_version_id === "ver-b");
    expect(flowB).toBeDefined();
    expect(flowB!.tool_display_name).toBe("Beta Tool");
    expect(flowB!.app_ids).toEqual(["conn-2", "conn-3"]);
  });

  it("handles empty connections array", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      // No connections set
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.connections).toEqual([]);
  });

  it("handles single flow vs multiple flows", () => {
    const { result: singleResult } = renderCreateHook();

    act(() => {
      singleResult.current.setDeploymentName("Single Flow Agent");
      singleResult.current.setSelectedLlm("model-1");
      singleResult.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
    });

    const singlePayload = singleResult.current.buildDeploymentPayload("p-1");
    expect(singlePayload.provider_data.add_flows).toHaveLength(1);
    expect(singlePayload.provider_data.add_flows[0].flow_version_id).toBe(
      "ver-1",
    );

    const { result: multiResult } = renderCreateHook();

    act(() => {
      multiResult.current.setDeploymentName("Multi Flow Agent");
      multiResult.current.setSelectedLlm("model-1");
      multiResult.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      multiResult.current.handleSelectVersion({
        flowId: "flow-2",
        flowName: "Flow",
        versionId: "ver-2",
        versionTag: "v2",
      });
      multiResult.current.handleSelectVersion({
        flowId: "flow-3",
        flowName: "Flow",
        versionId: "ver-3",
        versionTag: "v3",
      });
    });

    const multiPayload = multiResult.current.buildDeploymentPayload("p-1");
    expect(multiPayload.provider_data.add_flows).toHaveLength(3);
    const versionIds = multiPayload.provider_data.add_flows
      .map((f) => f.flow_version_id)
      .sort();
    expect(versionIds).toEqual(["ver-1", "ver-2", "ver-3"]);
  });

  it("uses a default tool display name when not set for a flow", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      // No tool name set
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.add_flows[0].tool_display_name).toBe("Flow");
  });

  it("uses a default tool display name when custom value is whitespace-only", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setDeploymentName("Agent");
      result.current.setSelectedLlm("model-1");
      result.current.handleSelectVersion({
        flowId: "flow-1",
        flowName: "Flow",
        versionId: "ver-1",
        versionTag: "v1",
      });
      result.current.setToolNameByFlow(new Map([["flow-1", "   "]]));
    });

    const payload = result.current.buildDeploymentPayload("p-1");
    expect(payload.provider_data.add_flows[0].tool_display_name).toBe("Flow");
  });
});

// ---------------------------------------------------------------------------
// buildProviderAccountPayload
// ---------------------------------------------------------------------------

describe("buildProviderAccountPayload", () => {
  it("includes name from credentials", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "My Provider Account",
        provider_key: "watsonx-orchestrate",
        url: "https://api.example.com",
        api_key: "key-abc", // pragma: allowlist secret
      });
    });

    const payload = result.current.buildProviderAccountPayload();
    expect(payload).not.toBeNull();
    expect(payload!.name).toBe("My Provider Account");
  });

  it("includes provider_data with url and api_key", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "Account",
        provider_key: "watsonx-orchestrate",
        url: "https://my-instance.example.com",
        api_key: "secret-key-xyz", // pragma: allowlist secret
      });
    });

    const payload = result.current.buildProviderAccountPayload();
    expect(payload).not.toBeNull();
    expect(payload!.provider_data).toEqual({
      url: "https://my-instance.example.com",
      api_key: "secret-key-xyz", // pragma: allowlist secret
    });
  });

  it("returns null when name is empty", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "",
        provider_key: "watsonx-orchestrate",
        url: "https://api.example.com",
        api_key: "key-123", // pragma: allowlist secret
      });
    });

    expect(result.current.buildProviderAccountPayload()).toBeNull();
  });

  it("returns null when url is empty", () => {
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

  it("returns null when api_key is empty", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "Account",
        provider_key: "watsonx-orchestrate",
        url: "https://api.example.com",
        api_key: "", // pragma: allowlist secret
      });
    });

    expect(result.current.buildProviderAccountPayload()).toBeNull();
  });

  it("trims whitespace from all fields", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "  My Account  ",
        provider_key: "watsonx-orchestrate",
        url: "  https://api.example.com  ",
        api_key: "  secret-key  ", // pragma: allowlist secret
      });
    });

    const payload = result.current.buildProviderAccountPayload();
    expect(payload).not.toBeNull();
    expect(payload!.name).toBe("My Account");
    expect(payload!.provider_data.url).toBe("https://api.example.com");
    expect(payload!.provider_data.api_key).toBe("secret-key");
  });

  it("returns null when all fields are whitespace-only", () => {
    const { result } = renderCreateHook();

    act(() => {
      result.current.setCredentials({
        name: "  ",
        provider_key: "watsonx-orchestrate",
        url: "  ",
        api_key: "  ", // pragma: allowlist secret
      });
    });

    expect(result.current.buildProviderAccountPayload()).toBeNull();
  });
});
