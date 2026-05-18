// usePatchUpdateFlow hook tests

const mockApiPatch = jest.fn();

const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: {
    patch: mockApiPatch,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key: string) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSettled?.(result);
        return result;
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

import { usePatchUpdateFlow } from "../use-patch-update-flow";

describe("usePatchUpdateFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_refresh_global_flows_cache_when_flow_is_moved_to_new_folder", async () => {
    // Arrange — backend responds with the updated flow (FlowRead)
    // carrying the new folder_id.
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-B" },
    });

    const mutation = usePatchUpdateFlow();

    // Act — simulate the drag-drop PATCH request.
    await mutation.mutate({
      id: "flow-1",
      folder_id: "folder-B",
    });

    // Assert — the global flows cache (useGetRefreshFlowsQuery) that
    // HomePage's `isEmptyFolder` check depends on must be invalidated
    // so stale entries in other folders are refreshed without a manual
    // page reload.
    const allInvalidateCalls = [
      ...mockQueryClient.invalidateQueries.mock.calls,
      ...mockQueryClient.refetchQueries.mock.calls,
    ];
    const invalidatesRefreshFlows = allInvalidateCalls.some((call) => {
      const queryKey = call[0]?.queryKey;
      return (
        Array.isArray(queryKey) && queryKey[0] === "useGetRefreshFlowsQuery"
      );
    });
    expect(invalidatesRefreshFlows).toBe(true);
  });

  it("should_invalidate_folders_list_query_with_correct_key_when_flow_is_patched", async () => {
    // Arrange
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-B" },
    });

    const mutation = usePatchUpdateFlow();

    // Act
    await mutation.mutate({
      id: "flow-1",
      folder_id: "folder-B",
    });

    // Assert — the folders list query key is ["useGetFolders"], so any
    // refetch must use that exact prefix. A composite key like
    // ["useGetFolders", <folder_id>] never matches the real cache entry.
    const allCalls = [
      ...mockQueryClient.invalidateQueries.mock.calls,
      ...mockQueryClient.refetchQueries.mock.calls,
    ];
    const matchesFoldersList = allCalls.some((call) => {
      const queryKey = call[0]?.queryKey;
      return (
        Array.isArray(queryKey) &&
        queryKey[0] === "useGetFolders" &&
        queryKey.length === 1
      );
    });
    expect(matchesFoldersList).toBe(true);
  });

  it("should_invalidate_individual_folder_queries_when_flow_is_patched", async () => {
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-B" },
    });

    const mutation = usePatchUpdateFlow();

    await mutation.mutate({
      id: "flow-1",
      folder_id: "folder-B",
    });

    const allCalls = [
      ...mockQueryClient.invalidateQueries.mock.calls,
      ...mockQueryClient.refetchQueries.mock.calls,
    ];
    const matchesIndividualFolder = allCalls.some((call) => {
      const queryKey = call[0]?.queryKey;
      return Array.isArray(queryKey) && queryKey[0] === "useGetFolder";
    });
    expect(matchesIndividualFolder).toBe(true);
  });
});
