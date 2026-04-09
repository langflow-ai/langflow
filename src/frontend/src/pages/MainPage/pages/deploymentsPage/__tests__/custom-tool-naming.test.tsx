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
    const addFlowItem = payload.provider_data.add_flows[0];
    expect(addFlowItem.tool_name).toBe("My Custom Tool");
  });

  it("buildDeploymentPayload omits tool_name when empty", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const addFlowItem = payload.provider_data.add_flows[0];
    expect(addFlowItem.tool_name).toBeUndefined();
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
    const addFlowItem = payload.provider_data.add_flows[0];
    expect(addFlowItem.tool_name).toBeUndefined();
  });

  it("tool name with special characters is preserved in payload", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setToolNameByFlow(
        new Map([["flow-1", "my-tool_v2.0 (beta) [test]"]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    expect(payload.provider_data.add_flows[0].tool_name).toBe(
      "my-tool_v2.0 (beta) [test]",
    );
  });

  it("tool name with unicode characters is preserved", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setToolNameByFlow(
        new Map([["flow-1", "ferramenta_análise"]]),
      );
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    expect(payload.provider_data.add_flows[0].tool_name).toBe(
      "ferramenta_análise",
    );
  });

  it("very long tool name is preserved without truncation", () => {
    const { result } = renderStepperHook();
    const longName = "A".repeat(500);

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.setToolNameByFlow(new Map([["flow-1", longName]]));
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    expect(payload.provider_data.add_flows[0].tool_name).toBe(longName);
    expect(payload.provider_data.add_flows[0].tool_name).toHaveLength(500);
  });

  it("two flows can have the same tool name (no client-side collision check)", () => {
    const { result } = renderStepperHook();

    act(() => {
      result.current.setDeploymentName("Test Agent");
      result.current.setSelectedLlm("test-model");
      result.current.handleSelectVersion("flow-1", "ver-1", "v1");
      result.current.handleSelectVersion("flow-2", "ver-2", "v2");
      result.current.setToolNameByFlow(
        new Map([
          ["flow-1", "Same Name"],
          ["flow-2", "Same Name"],
        ]),
      );
    });

    const payload = result.current.buildDeploymentPayload("provider-1");
    const addFlows = payload.provider_data.add_flows;
    expect(addFlows).toHaveLength(2);
    expect(addFlows[0].tool_name).toBe("Same Name");
    expect(addFlows[1].tool_name).toBe("Same Name");
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
    const addFlows = payload.provider_data.add_flows;
    expect(addFlows).toHaveLength(2);
    expect(addFlows.find((o) => o.flow_version_id === "ver-1")?.tool_name).toBe(
      "Tool Alpha",
    );
    expect(addFlows.find((o) => o.flow_version_id === "ver-2")?.tool_name).toBe(
      "Tool Beta",
    );
  });
});
