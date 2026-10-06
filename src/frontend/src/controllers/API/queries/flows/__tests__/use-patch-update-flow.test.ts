// usePatchUpdateFlow hook tests

const mockApiPatch = jest.fn();

const mockQueryClient = {
  cancelQueries: jest.fn().mockResolvedValue(undefined),
  resetQueries: jest.fn().mockResolvedValue(undefined),
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

interface PatchPayload {
  id: string;
  folder_id?: string | null;
  name?: string;
  providerScopeChanged?: boolean;
}

interface MutationCallbacks {
  onSuccess?: (
    result: unknown,
    payload: PatchPayload,
    context: unknown,
  ) => void | Promise<void>;
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
          await options?.onSuccess?.(result, payload, undefined);
          options?.onSettled?.(result, null, payload, undefined);
          return result;
        },
      }),
    ),
    queryClient: mockQueryClient,
  })),
}));

import { QueryClient, QueryObserver } from "@tanstack/react-query";
import {
  clearFlowScopedProviderQueries,
  usePatchUpdateFlow,
} from "../use-patch-update-flow";

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

  it("cancels and resets only flow-scoped provider caches after a successful project move", async () => {
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-B" },
    });

    const mutation = usePatchUpdateFlow();

    // The flow-scoped keys below hold data resolved while flow-1 belonged to
    // folder-A. The key only contains the flow id, so moving to folder-B must
    // explicitly reset each policy-filtered view. Invalidating alone retains
    // project A data while project B refetches or if that refetch fails.
    await mutation.mutate({
      id: "flow-1",
      folder_id: "folder-B",
      providerScopeChanged: true,
    });

    const cancelPredicateCall = mockQueryClient.cancelQueries.mock.calls.find(
      ([filters]) => typeof filters?.predicate === "function",
    );
    const resetPredicateCall = mockQueryClient.resetQueries.mock.calls.find(
      ([filters]) => typeof filters?.predicate === "function",
    );
    expect(cancelPredicateCall).toBeDefined();
    expect(resetPredicateCall).toBeDefined();
    const predicate = resetPredicateCall?.[0].predicate;

    const staleFlowAKeys = [
      ["useGetTypes", "flow-1", undefined],
      ["useGetModelProviders", true, undefined, "flow-1", undefined, undefined],
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
          undefined,
        ],
      }),
    ).toBe(false);
    expect(
      predicate({ queryKey: ["useGetTypes", "different-flow", undefined] }),
    ).toBe(false);
  });

  it("does not rehydrate project A policy data after moving the flow to project B", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const scopedKey = ["useGetTypes", "flow-1", undefined] as const;
    const globalKey = ["useGetTypes", undefined, undefined] as const;
    queryClient.setQueryData(scopedKey, { providers: ["project-A"] });
    queryClient.setQueryData(globalKey, { providers: ["global"] });
    const projectBQuery = jest.fn(async () => {
      throw new Error("project B policy unavailable");
    });
    const projectBObserver = new QueryObserver(queryClient, {
      queryKey: scopedKey,
      queryFn: projectBQuery,
      enabled: false,
      retry: false,
    });
    const unsubscribe = projectBObserver.subscribe(() => undefined);
    expect(projectBObserver.getCurrentResult().data).toEqual({
      providers: ["project-A"],
    });

    await clearFlowScopedProviderQueries(queryClient, "flow-1");

    expect(queryClient.getQueryData(scopedKey)).toBeUndefined();
    expect(projectBObserver.getCurrentResult().data).toBeUndefined();
    expect(queryClient.getQueryData(globalKey)).toEqual({
      providers: ["global"],
    });

    const failedProjectBResult = await projectBObserver.refetch();
    expect(failedProjectBResult.isError).toBe(true);
    expect(projectBQuery).toHaveBeenCalledTimes(1);
    expect(queryClient.getQueryData(scopedKey)).toBeUndefined();
    expect(projectBObserver.getCurrentResult().data).toBeUndefined();
    unsubscribe();
    queryClient.clear();
  });

  it("does not clear flow-scoped provider caches for a metadata-only patch", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "flow-1", name: "Renamed" } });

    const mutation = usePatchUpdateFlow();
    await mutation.mutate({ id: "flow-1", name: "Renamed" });

    expect(
      mockQueryClient.resetQueries.mock.calls.some(
        ([filters]) => typeof filters?.predicate === "function",
      ),
    ).toBe(false);
    expect(
      mockQueryClient.cancelQueries.mock.calls.some(
        ([filters]) => typeof filters?.predicate === "function",
      ),
    ).toBe(false);
  });

  it("does not clear flow-scoped provider caches when an ordinary save repeats folder_id", async () => {
    mockApiPatch.mockResolvedValue({
      data: { id: "flow-1", folder_id: "folder-A", name: "Saved" },
    });

    const mutation = usePatchUpdateFlow();
    await mutation.mutate({
      id: "flow-1",
      folder_id: "folder-A",
      name: "Saved",
    });

    expect(
      mockQueryClient.resetQueries.mock.calls.some(
        ([filters]) => typeof filters?.predicate === "function",
      ),
    ).toBe(false);
    expect(
      mockQueryClient.cancelQueries.mock.calls.some(
        ([filters]) => typeof filters?.predicate === "function",
      ),
    ).toBe(false);
  });
});
