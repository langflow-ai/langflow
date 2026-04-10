const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      // biome-ignore lint/suspicious/noExplicitAny: test mock
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSettled?.(result);
        return result;
      },
    })),
  })),
}));

import { useGetDeploymentExecution } from "../use-get-deployment-execution";
import type { DeploymentExecutionResponse } from "../use-post-deployment-execution";

describe("useGetDeploymentExecution", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls GET with encoded deployment_id and execution_id", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: { execution_id: "exec-1", status: "completed" },
    };
    mockApiGet.mockResolvedValue({ data: response });

    const mutation = useGetDeploymentExecution();
    await mutation.mutate({
      deployment_id: "dep-1",
      execution_id: "exec-1",
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-1/executions/exec-1",
    );
  });

  it("encodes special characters in execution_id", async () => {
    mockApiGet.mockResolvedValue({
      data: { deployment_id: "dep-1", provider_data: null },
    });

    const mutation = useGetDeploymentExecution();
    await mutation.mutate({
      deployment_id: "dep-1",
      execution_id: "exec/with spaces",
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-1/executions/exec%2Fwith%20spaces",
    );
  });

  it("returns execution status response", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        execution_id: "exec-1",
        status: "failed",
        last_error: "Model timeout",
        failed_at: "2026-01-01T00:00:05Z",
      },
    };
    mockApiGet.mockResolvedValue({ data: response });

    const mutation = useGetDeploymentExecution();
    const result = (await mutation.mutate({
      deployment_id: "dep-1",
      execution_id: "exec-1",
    })) as unknown as DeploymentExecutionResponse;

    expect(result).toEqual(response);
    expect(result.provider_data).toBeDefined();
    if (!result.provider_data) return;
    expect(result.provider_data.status).toBe("failed");
    expect(result.provider_data.last_error).toBe("Model timeout");
  });
});
