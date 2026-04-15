const mockApiPatch = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
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

import { usePatchSnapshot } from "../use-patch-snapshot";

describe("usePatchSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("patches snapshot URL with providerSnapshotId", async () => {
    mockApiPatch.mockResolvedValue({
      data: { flow_version_id: "fv-1", provider_snapshot_id: "snap-abc" },
    });

    const mutation = usePatchSnapshot();
    await mutation.mutate({
      providerSnapshotId: "snap-abc",
      flowVersionId: "fv-1",
    });

    expect(mockApiPatch).toHaveBeenCalledWith(
      "/api/v1/deployments/snapshots/snap-abc",
      { flow_version_id: "fv-1" },
    );
  });

  it("transforms flowVersionId to flow_version_id in body", async () => {
    mockApiPatch.mockResolvedValue({
      data: { flow_version_id: "fv-2", provider_snapshot_id: "snap-xyz" },
    });

    const mutation = usePatchSnapshot();
    await mutation.mutate({
      providerSnapshotId: "snap-xyz",
      flowVersionId: "fv-2",
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).toEqual({ flow_version_id: "fv-2" });
    expect(sentBody).not.toHaveProperty("flowVersionId");
    expect(sentBody).not.toHaveProperty("providerSnapshotId");
  });

  it("refetches useGetDeployments on success", async () => {
    mockApiPatch.mockResolvedValue({
      data: { flow_version_id: "fv-1", provider_snapshot_id: "snap-abc" },
    });

    const mutation = usePatchSnapshot();
    await mutation.mutate({
      providerSnapshotId: "snap-abc",
      flowVersionId: "fv-1",
    });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
  });

  it("returns snapshot update response", async () => {
    const responseData = {
      flow_version_id: "fv-1",
      provider_snapshot_id: "snap-abc",
    };
    mockApiPatch.mockResolvedValue({ data: responseData });

    const mutation = usePatchSnapshot();
    const result = await mutation.mutate({
      providerSnapshotId: "snap-abc",
      flowVersionId: "fv-1",
    });

    expect(result).toEqual(responseData);
  });
});
