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

import type { DeploymentRunRequest } from "../use-post-deployment-run";
import { usePostDeploymentRun } from "../use-post-deployment-run";

describe("usePostDeploymentRun", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts to runs endpoint with correct payload", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        id: "exec-1",
        status: "running",
      },
    };
    mockApiPost.mockResolvedValue({ data: response });

    const payload: DeploymentRunRequest = {
      deployment_id: "dep-1",
      provider_data: { input: "Hello agent" },
    };

    const mutation = usePostDeploymentRun();
    await mutation.mutate(payload);

    expect(mockApiPost).toHaveBeenCalledWith("/api/v1/deployments/dep-1/runs", {
      provider_data: { input: "Hello agent" },
    });
  });

  it("includes thread_id for multi-turn conversations", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        deployment_id: "dep-1",
        provider_data: { id: "exec-2", thread_id: "thread-1" },
      },
    });

    const payload: DeploymentRunRequest = {
      deployment_id: "dep-1",
      provider_data: { input: "Follow up", thread_id: "thread-1" },
    };

    const mutation = usePostDeploymentRun();
    await mutation.mutate(payload);

    const sentPayload = mockApiPost.mock.calls[0][1];
    expect(sentPayload.provider_data.thread_id).toBe("thread-1");
  });

  it("does not include agent_id in run request provider_data", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        deployment_id: "dep-1",
        provider_data: { id: "exec-3", status: "running" },
      },
    });

    const payload: DeploymentRunRequest = {
      deployment_id: "dep-1",
      provider_data: { input: "Hello from FE", thread_id: "thread-2" },
    };

    const mutation = usePostDeploymentRun();
    await mutation.mutate(payload);

    const sentPayload = mockApiPost.mock.calls[0][1];
    expect(sentPayload).toStrictEqual({
      provider_data: {
        input: "Hello from FE",
        thread_id: "thread-2",
      },
    });
    expect(sentPayload.provider_data).not.toHaveProperty("agent_id");
  });

  it("returns run response with provider_data", async () => {
    const response = {
      deployment_id: "dep-1",
      provider_data: {
        id: "exec-1",
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

    const mutation = usePostDeploymentRun();
    const result = await mutation.mutate({
      deployment_id: "dep-1",
      provider_data: { input: "Hi" },
    });

    expect(result).toEqual(response);
  });
});
