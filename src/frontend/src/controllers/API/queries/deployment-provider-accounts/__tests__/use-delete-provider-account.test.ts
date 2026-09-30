const mockApiDelete = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { delete: mockApiDelete },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments/providers"),
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

import { useDeleteProviderAccount } from "../use-delete-provider-account";

describe("useDeleteProviderAccount", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls DELETE with provider_id in URL", async () => {
    mockApiDelete.mockResolvedValue({});

    const mutation = useDeleteProviderAccount();
    await mutation.mutate({ provider_id: "prov-1" });

    expect(mockApiDelete).toHaveBeenCalledWith(
      "/api/v1/deployments/providers/prov-1",
    );
  });

  it("refetches useGetProviderAccounts on success", async () => {
    mockApiDelete.mockResolvedValue({});

    const mutation = useDeleteProviderAccount();
    await mutation.mutate({ provider_id: "prov-1" });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetProviderAccounts"],
    });
  });

  it("forwards caller onSuccess callback", async () => {
    mockApiDelete.mockResolvedValue({});

    const callerOnSuccess = jest.fn();
    const mutation = useDeleteProviderAccount({ onSuccess: callerOnSuccess });
    await mutation.mutate({ provider_id: "prov-1" });

    expect(callerOnSuccess).toHaveBeenCalled();
  });
});
