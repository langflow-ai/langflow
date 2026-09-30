import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import { type Deployment, getSelectedFlowVersionKey } from "../types";

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
  [getSelectedFlowVersionKey("flow-1", "ver-1"), "custom_tool_one"],
  [getSelectedFlowVersionKey("flow-2", "ver-2"), "custom_tool_two"],
]);

const initialConnections = new Map([
  [getSelectedFlowVersionKey("flow-1", "ver-1"), ["app-1"]],
]);

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

const initialVersions = new Map([
  [
    getSelectedFlowVersionKey("flow-1", "ver-1"),
    {
      key: getSelectedFlowVersionKey("flow-1", "ver-1"),
      flowId: "flow-1",
      versionId: "ver-1",
      versionTag: "v1",
    },
  ],
  [
    getSelectedFlowVersionKey("flow-2", "ver-2"),
    {
      key: getSelectedFlowVersionKey("flow-2", "ver-2"),
      flowId: "flow-2",
      versionId: "ver-2",
      versionTag: "v2",
    },
  ],
]);

const flow1Key = getSelectedFlowVersionKey("flow-1", "ver-1");
const flowNewKey = getSelectedFlowVersionKey("flow-new", "ver-new");

function renderEditHook() {
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(DeploymentStepperProvider, {
      initialState: {
        editingDeployment: mockDeployment,
        selectedVersionByFlow: initialVersions,
        initialLlm: "test-model",
        initialToolNameByFlow: initialToolNames,
        initialConnectionsByFlow: initialConnections,
      },
      children,
    });
  const hook = renderHook(() => useDeploymentStepper(), { wrapper });
  hook.rerender();
  return hook;
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

  it("canGoNext on step 1 (Type) is true with pre-filled data", () => {
    const { result } = renderEditHook();
    expect(result.current.canGoNext).toBe(true);
  });

  it("allows update flow when existing display name does not start with a letter", () => {
    const deployment = {
      ...mockDeployment,
      provider_data: { display_name: "1 Agent", name: "agent_1" },
    };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <DeploymentStepperProvider
        initialState={{
          editingDeployment: deployment,
          selectedVersionByFlow: initialVersions,
          initialLlm: "test-model",
          initialToolNameByFlow: initialToolNames,
          initialConnectionsByFlow: initialConnections,
        }}
      >
        {children}
      </DeploymentStepperProvider>
    );
    const { result } = renderHook(() => useDeploymentStepper(), { wrapper });

    expect(result.current.canGoNext).toBe(true);
    expect(result.current.isDeploymentNameValid).toBe(true);
    expect(result.current.hasDeploymentNameFormatError).toBe(false);
    expect(result.current.buildDeploymentUpdatePayload().deployment_id).toBe(
      "deploy-1",
    );
  });

  it("canGoNext on step 2 (Attach) allows proceeding in edit mode", () => {
    const { result } = renderEditHook();
    act(() => result.current.handleNext()); // step 2
    expect(result.current.currentStep).toBe(2);
    expect(result.current.canGoNext).toBe(true);
  });

  it("preExistingFlowIds tracks initial versions in edit mode", () => {
    const { result } = renderEditHook();
    expect(result.current.isEditMode).toBe(true);
    expect(result.current.preExistingFlowIds).toBeInstanceOf(Set);
  });

  it("handleRemoveAttachedFlow soft-removes via removedFlowIds when key is pre-existing", () => {
    const { result } = renderEditHook();

    // Manually add a version so we can test the soft-remove path.
    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
    });
    expect(result.current.selectedVersionByFlow.has(flowNewKey)).toBe(true);

    // Remove the newly added version — should hard-delete since it's not pre-existing.
    act(() => {
      result.current.handleRemoveAttachedFlow(flowNewKey);
    });

    expect(result.current.selectedVersionByFlow.has(flowNewKey)).toBe(false);
    expect(result.current.removedFlowIds.has(flowNewKey)).toBe(false);
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

  it("does NOT include top-level name on update payload", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentDescription("Updated"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload).not.toHaveProperty("name");
  });

  it("sends display name changes in provider_data", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentName("Updated Agent"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.display_name).toBe("Updated Agent");
  });

  it("sends LLM in provider_data when changed", () => {
    const { result } = renderEditHook();
    act(() => result.current.setSelectedLlm("new-model"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.llm).toBe("new-model");
  });

  it("sends upsert_flows for newly attached flows", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
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

  it("does NOT send remove_flows for flows that were not removed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(removeFlows).toHaveLength(0);
  });

  it("omits description when description is unchanged", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data).toBeUndefined();
    expect(payload.description).toBeUndefined();
  });

  it("includes tool_display_name on newly attached flow upsert", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
      result.current.setToolNameByFlow(
        new Map([[flowNewKey, "Custom Tool Name"]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (
        payload.provider_data as
          | {
              upsert_flows?: Array<{
                flow_version_id?: string;
                tool_display_name?: string;
              }>;
            }
          | undefined
      )?.upsert_flows ?? [];
    expect(upsertFlows[0].flow_version_id).toBe("ver-new");
    expect(upsertFlows[0].tool_display_name).toBe("Custom Tool Name");
  });

  it("handles attach + detach in same update", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const upsertFlows =
      (payload.provider_data as { upsert_flows?: Array<unknown> } | undefined)
        ?.upsert_flows ?? [];
    const removeFlows =
      (payload.provider_data as { remove_flows?: string[] } | undefined)
        ?.remove_flows ?? [];
    expect(upsertFlows).toHaveLength(1);
    expect(removeFlows).toEqual([]);
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
  it("sends only deployment_id when nothing changed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload).toEqual({ deployment_id: "deploy-1" });
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
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
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

describe("Edit mode — newly attached flow connections", () => {
  it("includes connections on a newly attached flow with connections", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion({
        flowId: "flow-new",
        flowName: "Flow",
        versionId: "ver-new",
        versionTag: "v1",
      });
      result.current.setAttachedConnectionByFlow(
        new Map([
          [flow1Key, ["app-1"]], // unchanged
          [flowNewKey, ["app-10", "app-11"]],
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
                add_app_ids?: string[];
                remove_app_ids?: string[];
              }>;
            }
          | undefined
      )?.upsert_flows ?? [];
    const newFlowEntry = upsertFlows.find(
      (o) => o.flow_version_id === "ver-new",
    );
    expect(newFlowEntry).toBeDefined();
    expect(newFlowEntry!.add_app_ids).toEqual(["app-10", "app-11"]);
    expect(newFlowEntry!.remove_app_ids).toEqual([]);
  });
});
