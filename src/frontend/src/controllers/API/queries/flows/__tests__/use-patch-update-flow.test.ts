// usePatchUpdateFlow hook tests

const mockApiPatch = jest.fn();

const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

interface PatchPayload {
  id: string;
  folder_id?: string | null;
  name?: string;
}

interface MutationCallbacks {
  onSuccess?: (
    result: unknown,
    payload: PatchPayload,
    context: unknown,
  ) => void;
  onSettled?: (
    result: unknown,
    error: unknown,
    payload: PatchPayload,
    context: unknown,
  ) => void;
}

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
    mutate: jest.fn(
      (
        _key: unknown,
        fn: (payload: PatchPayload) => Promise<unknown>,
        options: MutationCallbacks,
      ) => ({
        mutate: async (payload: PatchPayload) => {
          const result = await fn(payload);
          options?.onSuccess?.(result, payload, undefined);
          options?.onSettled?.(result, null, payload, undefined);
          return result;
        },
      }),
    ),
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

  it("invalidates only flow-scoped provider caches after a successful project move", async () => {
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-B" },
    });

    const mutation = usePatchUpdateFlow();

    // The flow-scoped keys below hold data resolved while flow-1 belonged to
    // folder-A. The key only contains the flow id, so moving to folder-B must
    // explicitly invalidate each policy-filtered view.
    await mutation.mutate({ id: "flow-1", folder_id: "folder-B" });

    const predicateCall = mockQueryClient.invalidateQueries.mock.calls.find(
      ([filters]) => typeof filters?.predicate === "function",
    );
    expect(predicateCall).toBeDefined();
    const predicate = predicateCall?.[0].predicate;

    const staleFlowAKeys = [
      ["useGetTypes", "flow-1", undefined],
      ["useGetModelProviders", true, undefined, "flow-1", undefined],
      ["useGetEnabledModels", "flow-1", undefined],
      ["useGetProviderVariables", "flow-1", undefined],
      ["useGetGlobalVariables", "flow-1", undefined],
    ];
    for (const queryKey of staleFlowAKeys) {
      expect(predicate({ queryKey })).toBe(true);
    }

    expect(
      predicate({
        queryKey: [
          "useGetModelProviders",
          true,
          undefined,
          undefined,
          undefined,
        ],
      }),
    ).toBe(false);
    expect(
      predicate({ queryKey: ["useGetTypes", "different-flow", undefined] }),
    ).toBe(false);
  });

  it("does not invalidate flow-scoped provider caches for a metadata-only patch", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "flow-1", name: "Renamed" } });

    const mutation = usePatchUpdateFlow();
    await mutation.mutate({ id: "flow-1", name: "Renamed" });

    expect(
      mockQueryClient.invalidateQueries.mock.calls.some(
        ([filters]) => typeof filters?.predicate === "function",
      ),
    ).toBe(false);
  });
});
