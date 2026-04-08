const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
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

import type { DeploymentExecutionRequest } from "../use-post-deployment-execution";
import { usePostDeploymentExecution } from "../use-post-deployment-execution";

describe("usePostDeploymentExecution", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts to executions endpoint with correct payload", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        execution_id: "exec-1",
        status: "running",
      },
    };
    mockApiPost.mockResolvedValue({ data: response });

    const payload: DeploymentExecutionRequest = {
      deployment_id: "dep-1",
      provider_data: { input: "Hello agent" },
    };

    const mutation = usePostDeploymentExecution();
    await mutation.mutate(payload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-1/executions",
      { provider_data: { input: "Hello agent" } },
    );
  });

  it("includes thread_id for multi-turn conversations", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        deployment_id: "dep-1",
        provider_data: { execution_id: "exec-2", thread_id: "thread-1" },
      },
    });

    const payload: DeploymentExecutionRequest = {
      deployment_id: "dep-1",
      provider_data: { input: "Follow up", thread_id: "thread-1" },
    };

    const mutation = usePostDeploymentExecution();
    await mutation.mutate(payload);

    const sentPayload = mockApiPost.mock.calls[0][1];
    expect(sentPayload.provider_data.thread_id).toBe("thread-1");
  });

  it("returns execution response with provider_data", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        execution_id: "exec-1",
        agent_id: "agent-1",
        status: "completed",
        result: { output: "Hello!" },
        thread_id: "thread-1",
        started_at: "2026-01-01T00:00:00Z",
        completed_at: "2026-01-01T00:00:01Z",
        failed_at: null,
        cancelled_at: null,
        last_error: null,
      },
    };
    mockApiPost.mockResolvedValue({ data: response });

    const mutation = usePostDeploymentExecution();
    const result = await mutation.mutate({
      deployment_id: "dep-1",
      provider_data: { input: "Hi" },
    });

    expect(result).toEqual(response);
  });
});
