const mockApiPatch = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  removeQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { patch: mockApiPatch },
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
        options?.onSuccess?.(result, payload, undefined);
        options?.onSettled?.(result);
        return result;
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

import type { DeploymentUpdateRequest } from "../use-patch-deployment";
import { usePatchDeployment } from "../use-patch-deployment";

describe("usePatchDeployment", () => {
  beforeEach(() => jest.clearAllMocks());

  it("patches correct URL with deployment_id and sends body without it", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const payload: DeploymentUpdateRequest = {
      deployment_id: "dep-1",
      spec: { description: "Updated description" },
      provider_data: { llm: "new-model" },
    };

    const mutation = usePatchDeployment();
    await mutation.mutate(payload);

    expect(mockApiPatch).toHaveBeenCalledWith("/api/v1/deployments/dep-1", {
      spec: { description: "Updated description" },
      provider_data: { llm: "new-model" },
    });
  });

  it("does not include deployment_id in request body", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      spec: { name: "Renamed" },
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).not.toHaveProperty("deployment_id");
  });

  it("refetches deployments and removes stale queries on success", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      spec: { description: "x" },
    });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
    expect(mockQueryClient.removeQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeploymentAttachments"],
    });
    expect(mockQueryClient.removeQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployment"],
    });
  });

  it("forwards caller onSuccess callback", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const callerOnSuccess = jest.fn();
    const mutation = usePatchDeployment({ onSuccess: callerOnSuccess });
    await mutation.mutate({ deployment_id: "dep-1", spec: {} });

    expect(callerOnSuccess).toHaveBeenCalled();
  });
});
