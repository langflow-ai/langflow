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

import { useGetDeploymentRun } from "../use-get-deployment-run";
import type { DeploymentRunResponse } from "../use-post-deployment-run";

describe("useGetDeploymentRun", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls GET with encoded deployment_id and run_id", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: { id: "exec-1", status: "completed" },
    };
    mockApiGet.mockResolvedValue({ data: response });

    const mutation = useGetDeploymentRun();
    await mutation.mutate({
      deployment_id: "dep-1",
      run_id: "exec-1",
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-1/runs/exec-1",
    );
  });

  it("encodes special characters in run_id", async () => {
    mockApiGet.mockResolvedValue({
      data: { deployment_id: "dep-1", provider_data: null },
    });

    const mutation = useGetDeploymentRun();
    await mutation.mutate({
      deployment_id: "dep-1",
      run_id: "exec/with spaces",
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-1/runs/exec%2Fwith%20spaces",
    );
  });

  it("returns run status response", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        id: "exec-1",
        status: "failed",
        last_error: "Model timeout",
        failed_at: "2026-01-01T00:00:05Z",
      },
    };
    mockApiGet.mockResolvedValue({ data: response });

    const mutation = useGetDeploymentRun();
    const result = (await mutation.mutate({
      deployment_id: "dep-1",
      run_id: "exec-1",
    })) as unknown as DeploymentRunResponse;

    expect(result).toEqual(response);
    expect(result.provider_data).toBeDefined();
    if (!result.provider_data) return;
    expect(result.provider_data.status).toBe("failed");
    expect(result.provider_data.last_error).toBe("Model timeout");
  });
});
