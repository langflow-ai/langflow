import { act, renderHook } from "@testing-library/react";
import React from "react";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";

jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({ usePostProviderAccount: jest.fn() }),
);
jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: jest.fn(),
}));

function renderStepperHook() {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <DeploymentStepperProvider>{children}</DeploymentStepperProvider>
  );
  return renderHook(() => useDeploymentStepper(), { wrapper });
}

describe("Custom tool naming", () => {
  it("toolNameByFlow starts empty", () => {
    const { result } = renderStepperHook();
    expect(result.current.toolNameByFlow.size).toBe(0);
  });

  it("setToolNameByFlow updates the map", () => {
    const { result } = renderStepperHook();
    act(() => {
      result.current.setToolNameByFlow(new Map([["flow-1", "My Custom Tool"]]));
    });
    expect(result.current.toolNameByFlow.get("flow-1")).toBe("My Custom Tool");
  });

  it("buildDeploymentPayload includes tool_name when set", () => {
    const { result } = renderStepperHook();

    // Set up required fields
    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setToolNameByFlow(new Map([["flow-1", "My Custom Tool"]]));
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const bindOp = payload.provider_data.operations[0];
    expect(bindOp.tool_name).toBe("My Custom Tool");
  });

  it("buildDeploymentPayload omits tool_name when empty", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const bindOp = payload.provider_data.operations[0];
    expect(bindOp.tool_name).toBeUndefined();
  });

  it("buildDeploymentPayload omits tool_name when whitespace-only", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setToolNameByFlow(new Map([["flow-1", "   "]]));
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const bindOp = payload.provider_data.operations[0];
    expect(bindOp.tool_name).toBeUndefined();
  });

  it("each flow can have its own tool name", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "Tool Alpha"],
          ["flow-2", "Tool Beta"],
        ]),
      );
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const ops = payload.provider_data.operations;
    expect(ops).toHaveLength(2);
    expect(ops.find((o) => o.flow_version_id === "ver-1")?.tool_name).toBe(
      "Tool Alpha",
    );
    expect(ops.find((o) => o.flow_version_id === "ver-2")?.tool_name).toBe(
      "Tool Beta",
    );
  });
});
