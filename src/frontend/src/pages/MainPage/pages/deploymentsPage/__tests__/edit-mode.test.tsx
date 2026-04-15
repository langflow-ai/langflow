import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import type { Deployment } from "../types";

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

const initialToolNames = new Map([
  ["flow-1", "custom_tool_one"],
  ["flow-2", "custom_tool_two"],
]);

const initialConnections = new Map([["flow-1", ["app-1"]]]);

const mockDeployment: Deployment = {
  id: "deploy-1",
  name: "My Agent",
  description: "A test agent",
  type: "agent",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  resource_key: "my-agent-key",
  attached_count: 2,
};

const initialVersions = new Map([
  ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
  ["flow-2", { versionId: "ver-2", versionTag: "v2" }],
]);

function renderEditHook() {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <DeploymentStepperProvider
      initialState={{
        editingDeployment: mockDeployment,
        selectedVersionByFlow: initialVersions,
        initialLlm: "test-model",
        initialToolNameByFlow: initialToolNames,
        initialConnectionsByFlow: initialConnections,
      }}
    >
      {children}
    </DeploymentStepperProvider>
  );
  return renderHook(() => useDeploymentStepper(), { wrapper });
}

describe("Edit mode — basic state", () => {
  it("starts in edit mode with 3 steps", () => {
    const { result } = renderEditHook();
    expect(result.current.isEditMode).toBe(true);
    expect(result.current.totalSteps).toBe(3);
    expect(result.current.currentStep).toBe(1);
    expect(result.current.editingDeployment).toEqual(mockDeployment);
  });

  it("pre-fills name, description, type from deployment", () => {
    const { result } = renderEditHook();
    expect(result.current.deploymentName).toBe("My Agent");
    expect(result.current.deploymentDescription).toBe("A test agent");
    expect(result.current.deploymentType).toBe("agent");
  });

  it("pre-fills LLM from initialLlm", () => {
    const { result } = renderEditHook();
    expect(result.current.selectedLlm).toBe("test-model");
  });

  it("pre-fills selectedVersionByFlow", () => {
    const { result } = renderEditHook();
    expect(result.current.selectedVersionByFlow.size).toBe(2);
    expect(result.current.selectedVersionByFlow.get("flow-1")).toEqual({
      versionId: "ver-1",
      versionTag: "v1",
    });
  });

  it("canGoNext on step 1 (Type) is true with pre-filled data", () => {
    const { result } = renderEditHook();
    expect(result.current.canGoNext).toBe(true);
  });

  it("canGoNext on step 2 (Attach) allows proceeding in edit mode", () => {
    const { result } = renderEditHook();
    act(() => result.current.handleNext()); // step 2
    expect(result.current.currentStep).toBe(2);
    expect(result.current.canGoNext).toBe(true);
  });
});

describe("Edit mode — detach flows", () => {
  it("removedFlowIds starts empty", () => {
    const { result } = renderEditHook();
    expect(result.current.removedFlowIds.size).toBe(0);
  });

  it("handleRemoveAttachedFlow removes from maps and adds to removedFlowIds", () => {
    const { result } = renderEditHook();

    act(() => result.current.handleRemoveAttachedFlow("flow-1"));

    expect(result.current.removedFlowIds.has("flow-1")).toBe(true);
    expect(result.current.selectedVersionByFlow.has("flow-1")).toBe(false);
    // flow-2 unaffected
    expect(result.current.selectedVersionByFlow.has("flow-2")).toBe(true);
  });

  it("handleUndoRemoveFlow restores the flow", () => {
    const { result } = renderEditHook();

    act(() => result.current.handleRemoveAttachedFlow("flow-1"));
    expect(result.current.removedFlowIds.has("flow-1")).toBe(true);

    act(() => result.current.handleUndoRemoveFlow("flow-1"));
    expect(result.current.removedFlowIds.has("flow-1")).toBe(false);
    expect(result.current.selectedVersionByFlow.has("flow-1")).toBe(true);
    expect(result.current.selectedVersionByFlow.get("flow-1")).toEqual({
      versionId: "ver-1",
      versionTag: "v1",
    });
  });
});

describe("Edit mode — buildDeploymentUpdatePayload", () => {
  it("includes deployment_id", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.deployment_id).toBe("deploy-1");
  });

  it("sends description change at top level", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentDescription("Updated description"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.description).toBe("Updated description");
  });

  it("does NOT include name on update payload", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentDescription("Updated"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.name).toBeUndefined();
  });

  it("sends LLM in provider_data", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.llm).toBe("test-model");
  });

  it("does NOT send upsert_flows for unchanged pre-existing flows", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(0);
  });

  it("sends upsert_flows for newly attached flows", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as
          | {
              upsert_flows?: Array<{
                flow_version_id?: string;
                add_app_ids?: string[];
                remove_app_ids?: string[];
              }>;
            }
          | undefined
      )?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-new");
    expect(upsertFlows[0].add_app_ids).toEqual([]);
    expect(upsertFlows[0].remove_app_ids).toEqual([]);
  });

  it("sends remove_flows for detached flows", () => {
    const { result } = renderEditHook();

    act(() => result.current.handleRemoveAttachedFlow("flow-1"));

    const payload = result.current.buildDeploymentUpdatePayload();
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(removeFlows).toEqual(["ver-1"]);
  });

  it("does NOT send remove_flows for flows that were not removed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(removeFlows).toHaveLength(0);
  });

  it("sends fallback description when nothing changed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    // LLM is set so provider_data exists, but also check spec fallback logic
    expect(payload.provider_data).toBeDefined();
  });

  it("includes tool_name on newly attached flow upsert", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
      result.current.setToolNameByFlow(
        new Map([["flow-new", "Custom Tool Name"]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as
          | {
              upsert_flows?: Array<{
                flow_version_id?: string;
                tool_name?: string;
              }>;
            }
          | undefined
      )?.upsert_flows ?? [];
    expect(upsertFlows[0].flow_version_id).toBe("ver-new");
    expect(upsertFlows[0].tool_name).toBe("Custom Tool Name");
  });

  it("handles attach + detach in same update", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleRemoveAttachedFlow("flow-1");
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(removeFlows).toEqual(["ver-1"]);
  });
});

describe("Edit mode — throws outside edit mode", () => {
  it("buildDeploymentUpdatePayload throws when not editing", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <DeploymentStepperProvider>{children}</DeploymentStepperProvider>
    );
    const { result } = renderHook(() => useDeploymentStepper(), { wrapper });
    expect(() => result.current.buildDeploymentUpdatePayload()).toThrow(
      "buildDeploymentUpdatePayload called outside edit mode",
    );
  });
});

describe("Edit mode — no-op and partial update payloads", () => {
  it("sends fallback spec when nothing changed at all", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    // LLM is pre-filled so provider_data always has llm
    expect(payload.deployment_id).toBe("deploy-1");
    expect(payload.provider_data?.llm).toBe("test-model");
    // No spec change → no spec field (or fallback if no provider_data either)
  });

  it("sends only description in spec when only description changed", () => {
    const { result } = renderEditHook();

    act(() => result.current.setDeploymentDescription("New description only"));

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.description).toBe("New description only");
    // No upsert_flows since no flows changed
    const upsertFlows =
      (payload.provider_data?.upsert_flows as Array<unknown>) ?? [];
    expect(upsertFlows).toHaveLength(0);
  });

  it("sends only LLM change without spec when description unchanged", () => {
    const { result } = renderEditHook();

    act(() => result.current.setSelectedLlm("new-model"));

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.llm).toBe("new-model");
    expect(payload.description).toBeUndefined();
  });

  it("sends only flow operations when only flows changed", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data?.upsert_flows as Array<{
        flow_version_id?: string;
      }>) ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-new");
    // Description didn't change → no description field
    expect(payload.description).toBeUndefined();
  });
});

describe("Edit mode — detach then re-attach same flow", () => {
  it("re-attaching a detached flow restores it to selectedVersionByFlow", () => {
    const { result } = renderEditHook();

    // Detach flow-1
    act(() => result.current.handleRemoveAttachedFlow("flow-1"));
    expect(result.current.removedFlowIds.has("flow-1")).toBe(true);
    expect(result.current.selectedVersionByFlow.has("flow-1")).toBe(false);

    // Re-attach via undo
    act(() => result.current.handleUndoRemoveFlow("flow-1"));
    expect(result.current.removedFlowIds.has("flow-1")).toBe(false);
    expect(result.current.selectedVersionByFlow.get("flow-1")).toEqual({
      versionId: "ver-1",
      versionTag: "v1",
    });

    // Payload should have no remove_flows or upsert_flows for flow-1 (it's back to original)
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data?.upsert_flows as Array<{
        flow_version_id?: string;
      }>) ?? [];
    const removeFlows = (payload.provider_data?.remove_flows as string[]) ?? [];
    expect(
      upsertFlows.filter((o) => o.flow_version_id === "ver-1"),
    ).toHaveLength(0);
    expect(removeFlows.includes("ver-1")).toBe(false);
  });

  it("detaching all flows then re-attaching one produces correct ops", () => {
    const { result } = renderEditHook();

    // Detach both
    act(() => {
      result.current.handleRemoveAttachedFlow("flow-1");
      result.current.handleRemoveAttachedFlow("flow-2");
    });
    expect(result.current.removedFlowIds.size).toBe(2);

    // Re-attach only flow-2
    act(() => result.current.handleUndoRemoveFlow("flow-2"));

    const payload = result.current.buildDeploymentUpdatePayload();
    const removeFlows = (payload.provider_data?.remove_flows as string[]) ?? [];
    const upsertFlows =
      (payload.provider_data?.upsert_flows as Array<{
        flow_version_id?: string;
      }>) ?? [];

    // flow-1 should be in remove_flows
    expect(removeFlows).toHaveLength(1);
    expect(removeFlows[0]).toBe("ver-1");

    // flow-2 was undone, so it should not be in remove_flows or upsert_flows
    expect(removeFlows.includes("ver-2")).toBe(false);
    expect(
      upsertFlows.filter((o) => o.flow_version_id === "ver-2"),
    ).toHaveLength(0);
  });
});

describe("Edit mode — pre-populated provider data", () => {
  it("pre-fills toolNameByFlow from initialToolNameByFlow", () => {
    const { result } = renderEditHook();
    expect(result.current.toolNameByFlow.get("flow-1")).toBe("custom_tool_one");
    expect(result.current.toolNameByFlow.get("flow-2")).toBe("custom_tool_two");
  });

  it("pre-fills attachedConnectionByFlow from initialConnectionsByFlow", () => {
    const { result } = renderEditHook();
    expect(result.current.attachedConnectionByFlow.get("flow-1")).toEqual([
      "app-1",
    ]);
  });

  it("preExistingFlowIds contains initially attached flows", () => {
    const { result } = renderEditHook();
    expect(result.current.preExistingFlowIds.has("flow-1")).toBe(true);
    expect(result.current.preExistingFlowIds.has("flow-2")).toBe(true);
    expect(result.current.preExistingFlowIds.has("flow-new")).toBe(false);
  });
});

describe("Edit mode — connection updates on pre-existing flows", () => {
  const upsertFlowType = {} as {
    upsert_flows?: Array<{
      flow_version_id?: string;
      add_app_ids?: string[];
      remove_app_ids?: string[];
      tool_name?: string;
    }>;
    connections?: Array<unknown>;
  };

  it("sends add_app_ids when adding a connection to a pre-existing flow", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["app-1", "app-2"]]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-1");
    expect(upsertFlows[0].add_app_ids).toEqual(["app-2"]);
    expect(upsertFlows[0].remove_app_ids).toEqual([]);
  });

  it("sends remove_app_ids when removing a connection from a pre-existing flow", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", []]]), // removed app-1
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-1");
    expect(upsertFlows[0].add_app_ids).toEqual([]);
    expect(upsertFlows[0].remove_app_ids).toEqual(["app-1"]);
  });

  it("sends both add and remove when swapping connections on a pre-existing flow", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["app-2", "app-3"]]]), // removed app-1, added app-2 & app-3
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].add_app_ids).toEqual(["app-2", "app-3"]);
    expect(upsertFlows[0].remove_app_ids).toEqual(["app-1"]);
  });

  it("does NOT send upsert for pre-existing flow when connections are unchanged", () => {
    const { result } = renderEditHook();
    // flow-1 starts with ["app-1"], no changes
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    // No flows should appear since nothing changed
    expect(
      upsertFlows.filter((o) => o.flow_version_id === "ver-1"),
    ).toHaveLength(0);
  });

  it("sends connection changes alongside tool_name rename on the same flow", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["app-1", "app-2"]]]),
      );
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "renamed_tool"],
          ["flow-2", "custom_tool_two"],
        ]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-1");
    expect(upsertFlows[0].tool_name).toBe("renamed_tool");
    expect(upsertFlows[0].add_app_ids).toEqual(["app-2"]);
    expect(upsertFlows[0].remove_app_ids).toEqual([]);
  });

  it("includes connections on a newly attached flow with connections", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
      result.current.setAttachedConnectionByFlow(
        new Map([
          ["flow-1", ["app-1"]], // unchanged
          ["flow-new", ["app-10", "app-11"]],
        ]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as typeof upsertFlowType)?.upsert_flows ?? [];
    const newFlowEntry = upsertFlows.find(
      (o) => o.flow_version_id === "ver-new",
    );
    expect(newFlowEntry).toBeDefined();
    expect(newFlowEntry!.add_app_ids).toEqual(["app-10", "app-11"]);
    expect(newFlowEntry!.remove_app_ids).toEqual([]);
  });
});

describe("Edit mode — undo restores connections", () => {
  it("handleUndoRemoveFlow restores connections from initialConnectionsByFlow", () => {
    const { result } = renderEditHook();

    // flow-1 starts with connections ["app-1"]
    act(() => result.current.handleRemoveAttachedFlow("flow-1"));
    expect(result.current.attachedConnectionByFlow.has("flow-1")).toBe(false);

    act(() => result.current.handleUndoRemoveFlow("flow-1"));
    expect(result.current.attachedConnectionByFlow.get("flow-1")).toEqual([
      "app-1",
    ]);

    // Payload should show no connection diff since it's restored to original
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as {
          upsert_flows?: Array<{ flow_version_id?: string }>;
        }
      )?.upsert_flows ?? [];
    expect(
      upsertFlows.filter((o) => o.flow_version_id === "ver-1"),
    ).toHaveLength(0);
  });
});

describe("Edit mode — tool_name updates", () => {
  it("sends upsert_flows tool_name for renamed pre-existing flow", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "renamed_tool"],
          ["flow-2", "custom_tool_two"],
        ]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as
          | {
              upsert_flows?: Array<{
                flow_version_id?: string;
                tool_name?: string;
                add_app_ids?: string[];
                remove_app_ids?: string[];
              }>;
            }
          | undefined
      )?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(upsertFlows[0].flow_version_id).toBe("ver-1");
    expect(upsertFlows[0].tool_name).toBe("renamed_tool");
    expect(upsertFlows[0].add_app_ids).toEqual([]);
    expect(upsertFlows[0].remove_app_ids).toEqual([]);
  });

  it("does NOT send tool_name upsert when name is unchanged", () => {
    const { result } = renderEditHook();
    // toolNameByFlow is pre-filled with initialToolNames, no changes
    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(0);
  });

  it("does NOT send tool_name upsert when name is cleared", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setToolNameByFlow(
        new Map([["flow-2", "custom_tool_two"]]),
      ); // flow-1 removed from map
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    expect(upsertFlows).toHaveLength(0);
  });
});
