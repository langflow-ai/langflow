const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments"),
}));

// Capture the config passed to useQueries so we can test combine and queryFn
// biome-ignore lint/suspicious/noExplicitAny: test mock
let capturedConfig: any = null;
jest.mock("@tanstack/react-query", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test mock
  useQueries: jest.fn((config: any) => {
    capturedConfig = config;
    // Simulate executing the combine function with mock results
    return config.combine
      ? config.combine([])
      : { deployments: [], isLoading: false };
  }),
}));

import { useQueries } from "@tanstack/react-query";
import { useGetDeploymentsByProviders } from "../use-get-deployments-by-providers";

describe("useGetDeploymentsByProviders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedConfig = null;
  });

  it("creates one query per provider ID", () => {
    useGetDeploymentsByProviders(["prov-1", "prov-2", "prov-3"]);

    expect(useQueries).toHaveBeenCalledTimes(1);
    expect(capturedConfig.queries).toHaveLength(3);
  });

  it("uses correct query key per provider", () => {
    useGetDeploymentsByProviders(["prov-1", "prov-2"]);

    expect(capturedConfig.queries[0].queryKey).toEqual([
      "useGetDeployments",
      { provider_id: "prov-1", page: 1, size: 20 },
    ]);
    expect(capturedConfig.queries[1].queryKey).toEqual([
      "useGetDeployments",
      { provider_id: "prov-2", page: 1, size: 20 },
    ]);
  });

  it("disables query when provider ID is empty", () => {
    useGetDeploymentsByProviders(["prov-1", ""]);

    expect(capturedConfig.queries[0].enabled).toBe(true);
    expect(capturedConfig.queries[1].enabled).toBe(false);
  });

  it("calls fetchDeployments with correct API params", async () => {
    mockApiGet.mockResolvedValue({
      data: { deployments: [], page: 1, size: 20, total: 0 },
    });

    useGetDeploymentsByProviders(["prov-1"]);
    await capturedConfig.queries[0].queryFn();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments", {
      params: { provider_id: "prov-1", page: 1, size: 20 },
    });
  });

  it("combine merges deployments and injects provider_account_id", () => {
    useGetDeploymentsByProviders(["prov-1", "prov-2"]);

    const mockResults = [
      {
        data: {
          deployments: [
            { id: "d1", name: "Agent 1" },
            { id: "d2", name: "Agent 2" },
          ],
        },
        isLoading: false,
      },
      {
        data: {
          deployments: [{ id: "d3", name: "Agent 3" }],
        },
        isLoading: false,
      },
    ];

    const combined = capturedConfig.combine(mockResults);

    expect(combined.deployments).toHaveLength(3);
    expect(combined.deployments[0]).toEqual(
      expect.objectContaining({ id: "d1", provider_account_id: "prov-1" }),
    );
    expect(combined.deployments[2]).toEqual(
      expect.objectContaining({ id: "d3", provider_account_id: "prov-2" }),
    );
    expect(combined.isLoading).toBe(false);
  });

  it("combine reports isLoading when any query is loading", () => {
    useGetDeploymentsByProviders(["prov-1", "prov-2"]);

    const mockResults = [
      { data: { deployments: [] }, isLoading: false },
      { data: undefined, isLoading: true },
    ];

    const combined = capturedConfig.combine(mockResults);

    expect(combined.isLoading).toBe(true);
  });

  it("combine skips providers with no data yet", () => {
    useGetDeploymentsByProviders(["prov-1", "prov-2"]);

    const mockResults = [
      { data: undefined, isLoading: true },
      {
        data: { deployments: [{ id: "d1", name: "Agent" }] },
        isLoading: false,
      },
    ];

    const combined = capturedConfig.combine(mockResults);

    expect(combined.deployments).toHaveLength(1);
    expect(combined.deployments[0].provider_account_id).toBe("prov-2");
  });

  it("returns empty deployments for empty provider list", () => {
    useGetDeploymentsByProviders([]);

    expect(capturedConfig.queries).toHaveLength(0);
  });
});
