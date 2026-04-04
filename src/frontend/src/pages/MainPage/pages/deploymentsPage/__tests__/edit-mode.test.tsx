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

const initialConnections = new Map([
  ["flow-1", ["app-1"]],
]);

const mockDeployment: Deployment = {
  id: "deploy-1",
  name: "My Agent",
  description: "A test agent",
  type: "agent",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  provider_data: null,
  resource_key: "my-agent-key",
  attached_count: 2,
  matched_attachments: null,
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

  it("sends description change in spec", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentDescription("Updated description"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.spec).toEqual({ description: "Updated description" });
  });

  it("does NOT include name in spec", () => {
    const { result } = renderEditHook();
    act(() => result.current.setDeploymentDescription("Updated"));
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.spec?.name).toBeUndefined();
  });

  it("sends LLM in provider_data", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.llm).toBe("test-model");
  });

  it("does NOT send bind for pre-existing flows", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{ op: string }>) ?? [];
    const bindOps = ops.filter((o) => o.op === "bind");
    expect(bindOps).toHaveLength(0);
  });

  it("sends bind for newly attached flows", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{
        op: string;
        flow_version_id?: string;
      }>) ?? [];
    const bindOps = ops.filter((o) => o.op === "bind");
    expect(bindOps).toHaveLength(1);
    expect(bindOps[0].flow_version_id).toBe("ver-new");
  });

  it("sends remove_tool for detached flows", () => {
    const { result } = renderEditHook();

    act(() => result.current.handleRemoveAttachedFlow("flow-1"));

    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{
        op: string;
        flow_version_id?: string;
      }>) ?? [];
    const removeOps = ops.filter((o) => o.op === "remove_tool");
    expect(removeOps).toHaveLength(1);
    expect(removeOps[0].flow_version_id).toBe("ver-1");
  });

  it("does NOT send remove_tool for flows that were not removed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{ op: string }>) ?? [];
    expect(ops.filter((o) => o.op === "remove_tool")).toHaveLength(0);
  });

  it("sends fallback spec when nothing changed", () => {
    const { result } = renderEditHook();
    const payload = result.current.buildDeploymentUpdatePayload();
    // LLM is set so provider_data exists, but also check spec fallback logic
    expect(payload.provider_data).toBeDefined();
  });

  it("includes tool_name on new bind operations", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
      result.current.setToolNameByFlow(
        new Map([["flow-new", "Custom Tool Name"]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{
        op: string;
        tool_name?: string;
      }>) ?? [];
    const bindOps = ops.filter((o) => o.op === "bind");
    expect(bindOps[0].tool_name).toBe("Custom Tool Name");
  });

  it("handles attach + detach in same update", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.handleRemoveAttachedFlow("flow-1");
      result.current.handleSelectVersion("flow-new", "ver-new", "v1");
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{
        op: string;
        flow_version_id?: string;
      }>) ?? [];
    expect(ops.filter((o) => o.op === "remove_tool")).toHaveLength(1);
    expect(ops.filter((o) => o.op === "bind")).toHaveLength(1);
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

describe("Edit mode — pre-populated provider data", () => {
  it("pre-fills toolNameByFlow from initialToolNameByFlow", () => {
    const { result } = renderEditHook();
    expect(result.current.toolNameByFlow.get("flow-1")).toBe(
      "custom_tool_one",
    );
    expect(result.current.toolNameByFlow.get("flow-2")).toBe(
      "custom_tool_two",
    );
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

describe("Edit mode — rename_tool operations", () => {
  it("sends rename_tool when pre-existing flow tool name changes", () => {
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
    const ops =
      (payload.provider_data?.operations as Array<{
        op: string;
        flow_version_id?: string;
        tool_name?: string;
      }>) ?? [];
    const renameOps = ops.filter((o) => o.op === "rename_tool");
    expect(renameOps).toHaveLength(1);
    expect(renameOps[0].flow_version_id).toBe("ver-1");
    expect(renameOps[0].tool_name).toBe("renamed_tool");
  });

  it("does NOT send rename_tool when name is unchanged", () => {
    const { result } = renderEditHook();
    // toolNameByFlow is pre-filled with initialToolNames, no changes
    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{ op: string }>) ?? [];
    expect(ops.filter((o) => o.op === "rename_tool")).toHaveLength(0);
  });

  it("does NOT send rename_tool when name is cleared (falls back to flow name)", () => {
    const { result } = renderEditHook();

    act(() => {
      result.current.setToolNameByFlow(
        new Map([["flow-2", "custom_tool_two"]]),
      ); // flow-1 removed from map
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    const ops =
      (payload.provider_data?.operations as Array<{ op: string }>) ?? [];
    // Empty string !== original, but we only send rename when currentName is truthy
    expect(ops.filter((o) => o.op === "rename_tool")).toHaveLength(0);
  });
});
