const mockApiGet = jest.fn();
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options?: unknown) => {
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    const result: { data: any; isLoading: boolean; error: unknown } = {
      data: null,
      isLoading: false,
      error: null,
    };
    void fn().then((data) => {
      result.data = data;
    });
    return result;
  },
);

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments/providers"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({ query: mockQuery })),
}));

import { useGetProviderAccounts } from "../use-get-provider-accounts";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetProviderAccounts", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with default pagination", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_accounts: [], page: 1, size: 20, total: 0 },
    });

    useGetProviderAccounts({});
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/providers", {
      params: { page: 1, size: 20 },
    });
  });

  it("calls API with custom pagination", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_accounts: [], page: 2, size: 10, total: 15 },
    });

    useGetProviderAccounts({ page: 2, size: 10 });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/providers", {
      params: { page: 2, size: 10 },
    });
  });

  it("uses correct query key", () => {
    mockApiGet.mockResolvedValue({ data: { providers: [] } });

    useGetProviderAccounts({ page: 1, size: 20 });

    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetProviderAccounts", { page: 1, size: 20 }],
      expect.any(Function),
      undefined,
    );
  });

  it("returns provider accounts from response", async () => {
    const responseData = {
      provider_accounts: [
        {
          id: "prov-1",
          name: "My WxO",
          provider_tenant_id: "tenant-1",
          provider_key: "watsonx_orchestrate",
          provider_url: "https://api.wxo.ibm.com",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: null,
        },
      ],
      page: 1,
      size: 20,
      total: 1,
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    const result = useGetProviderAccounts({});
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(responseData);
    expect(result.data.provider_accounts).toHaveLength(1);
    expect(result.data.provider_accounts[0].provider_key).toBe(
      "watsonx_orchestrate",
    );
  });
});
