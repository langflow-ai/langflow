const mockApiDelete = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { delete: mockApiDelete },
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

import { useDeleteDeployment } from "../use-delete-deployment";

describe("useDeleteDeployment", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls DELETE with deployment_id in URL", async () => {
    mockApiDelete.mockResolvedValue({});

    const mutation = useDeleteDeployment();
    await mutation.mutate({ deployment_id: "dep-1" });

    expect(mockApiDelete).toHaveBeenCalledWith("/api/v1/deployments/dep-1");
  });

  it("refetches useGetDeployments on success", async () => {
    mockApiDelete.mockResolvedValue({});

    const mutation = useDeleteDeployment();
    await mutation.mutate({ deployment_id: "dep-1" });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
  });

  it("forwards caller onSuccess callback", async () => {
    mockApiDelete.mockResolvedValue({});

    const callerOnSuccess = jest.fn();
    const mutation = useDeleteDeployment({ onSuccess: callerOnSuccess });
    await mutation.mutate({ deployment_id: "dep-1" });

    expect(callerOnSuccess).toHaveBeenCalled();
  });
});
