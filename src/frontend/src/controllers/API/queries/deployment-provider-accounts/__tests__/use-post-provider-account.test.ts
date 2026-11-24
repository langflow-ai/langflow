const mockApiPost = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments/providers"),
}));

const mockMutate = jest.fn(
  // biome-ignore lint/suspicious/noExplicitAny: test mock
  (_key: any, fn: any, options: any) => ({
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    mutate: async (payload: any) => {
      const result = await fn(payload);
      options?.onSuccess?.(result);
      options?.onSettled?.(result);
      return result;
    },
  }),
);

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: mockMutate,
    queryClient: mockQueryClient,
  })),
}));

import type { ProviderAccountCreateRequest } from "../use-post-provider-account";
import { usePostProviderAccount } from "../use-post-provider-account";

describe("usePostProviderAccount", () => {
  beforeEach(() => jest.clearAllMocks());

  const validPayload: ProviderAccountCreateRequest = {
    name: "My WxO Environment",
    provider_key: "watsonx-orchestrate",
    provider_data: {
      url: "https://api.wxo.ibm.com",
      api_key: "secret-key", // pragma: allowlist secret
    },
  };

  it("posts to providers endpoint with full payload", async () => {
    mockApiPost.mockResolvedValue({
      data: { id: "prov-1", name: "My WxO Environment" },
    });

    const mutation = usePostProviderAccount();
    await mutation.mutate(validPayload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/deployments/providers",
      validPayload,
    );
  });

  it("sends api_key inside provider_data", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "prov-1" } });

    const mutation = usePostProviderAccount();
    await mutation.mutate(validPayload);

    const sentPayload = mockApiPost.mock.calls[0][1];
    expect(sentPayload.provider_data.api_key).toBe("secret-key");
  });

  it("refetches useGetProviderAccounts on success", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "prov-1" } });

    const mutation = usePostProviderAccount();
    await mutation.mutate(validPayload);

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetProviderAccounts"],
    });
  });

  it("disables automatic retries", () => {
    usePostProviderAccount();

    const options = mockMutate.mock.calls[0][2];
    expect(options.retry).toBe(0);
  });

  it("returns created provider account", async () => {
    const created = {
      id: "prov-1",
      name: "My WxO Environment",
      provider_key: "watsonx-orchestrate",
      provider_data: { url: "https://api.wxo.ibm.com", tenant_id: "tenant-1" },
      created_at: "2026-01-01T00:00:00Z",
      updated_at: null,
    };
    mockApiPost.mockResolvedValue({ data: created });

    const mutation = usePostProviderAccount();
    const result = await mutation.mutate(validPayload);

    expect(result).toEqual(created);
  });
});
