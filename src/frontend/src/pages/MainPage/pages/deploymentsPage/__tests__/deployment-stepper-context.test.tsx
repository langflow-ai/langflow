import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import { mockDeployment, mockDeploymentNoLlm, mockProviderAccount } from "./test-utils";

// Minimal mocks required by the context
jest.mock("@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account", () => ({
  usePostProviderAccount: jest.fn(),
}));
jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: jest.fn(),
}));
jest.mock("@/controllers/API/queries/deployments/use-patch-deployment", () => ({
  usePatchDeployment: jest.fn(),
}));

function renderStepperHook(initialState?: Parameters<typeof DeploymentStepperProvider>[0]["initialState"]) {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <DeploymentStepperProvider initialState={initialState}>
      {children}
    </DeploymentStepperProvider>
  );
  return renderHook(() => useDeploymentStepper(), { wrapper });
}

describe("DeploymentStepperContext – create mode (default)", () => {
  it("starts in create mode with 4 steps", () => {
    const { result } = renderStepperHook();
    expect(result.current.isEditMode).toBe(false);
    expect(result.current.totalSteps).toBe(4);
    expect(result.current.currentStep).toBe(1);
    expect(result.current.editingDeployment).toBeNull();
  });

  it("initialises with empty fields", () => {
    const { result } = renderStepperHook();
    expect(result.current.deploymentName).toBe("");
    expect(result.current.deploymentDescription).toBe("");
    expect(result.current.selectedLlm).toBe("");
    expect(result.current.deploymentType).toBe("agent");
  });

  it("navigates forward and backward", () => {
    const { result } = renderStepperHook();
    // Can't go next on step 1 without provider selection
    expect(result.current.canGoNext).toBe(false);

    // Manually advance to verify navigation logic
    act(() => result.current.handleNext());
    // Still step 1 because canGoNext guards are in the UI, handleNext always advances
    expect(result.current.currentStep).toBe(2);

    act(() => result.current.handleBack());
    expect(result.current.currentStep).toBe(1);

    // Can't go below step 1
    act(() => result.current.handleBack());
    expect(result.current.currentStep).toBe(1);
  });

  it("step 2 requires name and LLM", () => {
    const { result } = renderStepperHook();

    // Advance to step 2
    act(() => result.current.handleNext());
    expect(result.current.currentStep).toBe(2);
    expect(result.current.canGoNext).toBe(false);

    act(() => result.current.setDeploymentName("Test Agent"));
    expect(result.current.canGoNext).toBe(false); // still need LLM

    act(() => result.current.setSelectedLlm("ibm/granite-3-8b-instruct"));
    expect(result.current.canGoNext).toBe(true);
  });
});

describe("DeploymentStepperContext – edit mode", () => {
  it("starts in edit mode with 3 steps when editingDeployment provided", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    expect(result.current.isEditMode).toBe(true);
    expect(result.current.totalSteps).toBe(3);
    expect(result.current.currentStep).toBe(1);
    expect(result.current.editingDeployment).toEqual(mockDeployment);
  });

  it("pre-fills name, description, type, and LLM from existing deployment", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    expect(result.current.deploymentName).toBe("My Agent");
    expect(result.current.deploymentDescription).toBe("A test agent");
    expect(result.current.deploymentType).toBe("agent");
    expect(result.current.selectedLlm).toBe("ibm/granite-3-8b-instruct");
  });

  it("pre-fills provider account", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    expect(result.current.selectedInstance).toEqual(mockProviderAccount);
  });

  it("handles missing LLM in provider_data gracefully", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeploymentNoLlm,
    });
    expect(result.current.selectedLlm).toBe("");
  });

  it("handles null description gracefully", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeploymentNoLlm,
    });
    expect(result.current.deploymentDescription).toBe("");
  });

  it("step 1 in edit mode maps to Type step (requires name + LLM)", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    // Name and LLM are pre-filled, so canGoNext should be true on step 1
    expect(result.current.currentStep).toBe(1);
    expect(result.current.canGoNext).toBe(true);
  });

  it("Attach Flows step is optional in edit mode (can proceed with no new flows)", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    // Advance to step 2 (Attach Flows in edit mode)
    act(() => result.current.handleNext());
    expect(result.current.currentStep).toBe(2);
    // Should be able to proceed without attaching flows in edit mode
    expect(result.current.canGoNext).toBe(true);
  });

  it("cannot advance past totalSteps", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    act(() => result.current.handleNext()); // step 2
    act(() => result.current.handleNext()); // step 3
    act(() => result.current.handleNext()); // should stay at 3
    expect(result.current.currentStep).toBe(3);
  });
});

describe("DeploymentStepperContext – buildDeploymentUpdatePayload", () => {
  it("throws when called outside edit mode", () => {
    const { result } = renderStepperHook();
    expect(() => result.current.buildDeploymentUpdatePayload()).toThrow(
      "buildDeploymentUpdatePayload called outside edit mode",
    );
  });

  it("includes deployment_id", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.deployment_id).toBe("deploy-1");
  });

  it("does NOT include name in spec (name is not editable)", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    const payload = result.current.buildDeploymentUpdatePayload();
    // No changes made, fallback sends description
    expect(payload.spec?.name).toBeUndefined();
  });

  it("sends description change in spec when description is modified", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });

    act(() => result.current.setDeploymentDescription("Updated description"));

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.spec).toEqual({ description: "Updated description" });
    expect(payload.spec?.name).toBeUndefined();
  });

  it("sends provider_data when LLM is changed", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });

    act(() => result.current.setSelectedLlm("ibm/granite-3-2b-instruct"));

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data).toBeDefined();
    expect(payload.provider_data?.llm).toBe("ibm/granite-3-2b-instruct");
  });

  it("always sends LLM in provider_data (required by Watsonx)", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    // Don't change anything — LLM should still be in provider_data
    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.llm).toBe("ibm/granite-3-8b-instruct");
  });

  it("sends fallback spec when nothing changed and no LLM set", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeploymentNoLlm,
    });
    const payload = result.current.buildDeploymentUpdatePayload();
    // No LLM and no changes → fallback sends description
    expect(payload.spec).toBeDefined();
    expect(payload.spec?.description).toBe("");
  });

  it("never sends top-level add_flow_version_ids (Watsonx uses provider_data.operations)", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });

    act(() => {
      result.current.handleSelectVersion("flow-1", "version-abc", "v1.0");
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-1"]]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    // Must NOT have top-level flow version fields
    expect(payload.add_flow_version_ids).toBeUndefined();
    expect(payload.remove_flow_version_ids).toBeUndefined();
    expect(payload.config).toBeUndefined();
    // Instead, bind operations go through provider_data
    expect(payload.provider_data?.operations).toBeDefined();
  });

  it("includes operations and connections in provider_data when flows are attached", () => {
    const { result } = renderStepperHook({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });

    // Select a version and attach a connection
    act(() => {
      result.current.handleSelectVersion("flow-1", "version-abc", "v1.0");
      result.current.setAttachedConnectionByFlow(
        new Map([["flow-1", ["conn-existing"]]]),
      );
    });

    const payload = result.current.buildDeploymentUpdatePayload();
    expect(payload.provider_data?.operations).toEqual([
      { op: "bind", flow_version_id: "version-abc", app_ids: ["conn-existing"] },
    ]);
    expect(payload.provider_data?.connections).toEqual({
      existing_app_ids: ["conn-existing"],
      raw_payloads: [],
    });
  });
});
