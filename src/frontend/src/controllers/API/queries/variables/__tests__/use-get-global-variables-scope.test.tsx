import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import type { GlobalVariable } from "@/types/global_variables";

const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/variables",
}));

import {
  getGlobalVariablesQueryKey,
  useGetGlobalVariables,
} from "../use-get-global-variables";

const variable = (
  id: string,
  name: string,
  defaultField: string,
): GlobalVariable => ({
  id,
  name,
  type: "Credential",
  default_fields: [defaultField],
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

const makeWrapper = (queryClient: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

describe("useGetGlobalVariables store isolation", () => {
  beforeAll(() => {
    focusManager.setFocused(false);
  });

  beforeEach(() => {
    jest.clearAllMocks();
    focusManager.setFocused(false);
    onlineManager.setOnline(true);
    useAuthStore.setState({ isAuthenticated: true });
    useGlobalVariablesStore.setState({
      globalVariablesEntries: undefined,
      globalVariablesEntities: undefined,
      unavailableFields: {},
    });
  });

  afterAll(() => {
    focusManager.setFocused(undefined);
    onlineManager.setOnline(undefined);
  });

  it("keeps the explicitly mirrored global snapshot when a scoped request settles later", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const globalVariables = [variable("global-id", "GLOBAL_KEY", "System")];
    const flowVariables = [variable("flow-id", "PROJECT_KEY", "API Key")];
    const globalRequest = deferred<{ data: GlobalVariable[] }>();
    const flowRequest = deferred<{ data: GlobalVariable[] }>();
    mockApiGet.mockImplementation((url: string) =>
      url.includes("flow_id=flow-a")
        ? flowRequest.promise
        : globalRequest.promise,
    );
    renderHook(
      () => {
        useGetGlobalVariables({ mirrorToStore: true });
        useGetGlobalVariables({ flowId: "flow-a" });
      },
      { wrapper: makeWrapper(queryClient) },
    );

    await act(async () => globalRequest.resolve({ data: globalVariables }));
    await waitFor(() =>
      expect(useGlobalVariablesStore.getState().globalVariablesEntries).toEqual(
        ["GLOBAL_KEY"],
      ),
    );

    await act(async () => flowRequest.resolve({ data: flowVariables }));
    await waitFor(() =>
      expect(
        queryClient.getQueryData([
          "useGetGlobalVariables",
          "flow-a",
          undefined,
        ]),
      ).toEqual(flowVariables),
    );

    const state = useGlobalVariablesStore.getState();
    expect(state.globalVariablesEntries).toEqual(["GLOBAL_KEY"]);
    expect(state.globalVariablesEntities).toEqual(globalVariables);
    expect(state.unavailableFields).toEqual({ System: "GLOBAL_KEY" });
    queryClient.clear();
  });

  it("keeps A, B, and global responses in separate query entries", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const flowA = [variable("a-id", "FLOW_A_KEY", "A Field")];
    const flowB = [variable("b-id", "FLOW_B_KEY", "B Field")];
    const global = [variable("global-id", "GLOBAL_KEY", "System")];
    mockApiGet.mockImplementation((url: string) => {
      if (url.includes("flow_id=flow-a"))
        return Promise.resolve({ data: flowA });
      if (url.includes("flow_id=flow-b"))
        return Promise.resolve({ data: flowB });
      return Promise.resolve({ data: global });
    });

    const { result, rerender } = renderHook(
      ({ flowId, mirrorToStore }: ScopeProps) =>
        useGetGlobalVariables({ flowId, mirrorToStore }),
      {
        initialProps: {
          flowId: "flow-a",
          mirrorToStore: false,
        } as ScopeProps,
        wrapper: makeWrapper(queryClient),
      },
    );

    await waitFor(() => expect(result.current.data).toEqual(flowA));
    rerender({ flowId: "flow-b", mirrorToStore: false });
    await waitFor(() => expect(result.current.data).toEqual(flowB));
    rerender({ flowId: undefined, mirrorToStore: true });
    await waitFor(() => expect(result.current.data).toEqual(global));

    expect(
      queryClient.getQueryData(["useGetGlobalVariables", "flow-a", undefined]),
    ).toEqual(flowA);
    expect(
      queryClient.getQueryData(["useGetGlobalVariables", "flow-b", undefined]),
    ).toEqual(flowB);
    expect(
      queryClient.getQueryData(["useGetGlobalVariables", undefined, undefined]),
    ).toEqual(global);
    expect(useGlobalVariablesStore.getState().globalVariablesEntries).toEqual([
      "GLOBAL_KEY",
    ]);
    queryClient.clear();
  });

  it("revalidates scoped credentials when the window regains focus", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const initialVariables = [
      variable("initial-id", "INITIAL_KEY", "Initial Field"),
    ];
    const refreshedVariables = [
      variable("refreshed-id", "REFRESHED_KEY", "Refreshed Field"),
    ];
    const refreshRequest = deferred<{ data: GlobalVariable[] }>();
    mockApiGet.mockResolvedValue({ data: initialVariables });

    const { result } = renderHook(
      () =>
        useGetGlobalVariables({
          flowId: "flow-a",
          refetchOnWindowFocus: false,
          retry: false,
        }),
      { wrapper: makeWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.data).toEqual(initialVariables));
    mockApiGet.mockReset();
    mockApiGet.mockImplementationOnce(() => refreshRequest.promise);

    act(() => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toBeUndefined();

    await act(async () => refreshRequest.resolve({ data: refreshedVariables }));
    await waitFor(() =>
      expect(result.current.data).toEqual(refreshedVariables),
    );
    focusManager.setFocused(false);
    queryClient.clear();
  });

  it("keeps scoped credentials hidden after a focus refetch fails", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const initialVariables = [
      variable("initial-id", "INITIAL_KEY", "Initial Field"),
    ];
    const refreshRequest = deferred<{ data: GlobalVariable[] }>();
    mockApiGet.mockResolvedValue({ data: initialVariables });

    const { result } = renderHook(
      () => useGetGlobalVariables({ flowId: "flow-a", retry: false }),
      { wrapper: makeWrapper(queryClient) },
    );
    await waitFor(() => expect(result.current.data).toEqual(initialVariables));
    mockApiGet.mockReset();
    mockApiGet.mockImplementationOnce(() => refreshRequest.promise);

    act(() => {
      focusManager.setFocused(true);
    });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toBeUndefined();

    await act(async () => refreshRequest.reject(new Error("scope denied")));
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    focusManager.setFocused(false);
    queryClient.clear();
  });

  it("keeps cached scoped credentials hidden while an offline refresh is paused", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const initialVariables = [
      variable("initial-id", "INITIAL_KEY", "Initial Field"),
    ];
    mockApiGet.mockResolvedValue({ data: initialVariables });

    const { result } = renderHook(
      () => useGetGlobalVariables({ flowId: "flow-a", retry: false }),
      { wrapper: makeWrapper(queryClient) },
    );
    await waitFor(() => expect(result.current.data).toEqual(initialVariables));

    act(() => onlineManager.setOnline(false));
    act(() => {
      void queryClient.invalidateQueries({
        queryKey: getGlobalVariablesQueryKey({ flowId: "flow-a" }),
        exact: true,
      });
    });

    await waitFor(() => expect(result.current.fetchStatus).toBe("paused"));
    expect(result.current.data).toBeUndefined();

    onlineManager.setOnline(true);
    queryClient.clear();
  });

  it("preserves unscoped Settings data during an explicit refresh", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const initialVariables = [
      variable("initial-id", "INITIAL_KEY", "Initial Field"),
    ];
    const refreshedVariables = [
      variable("refreshed-id", "REFRESHED_KEY", "Refreshed Field"),
    ];
    const refreshRequest = deferred<{ data: GlobalVariable[] }>();
    mockApiGet.mockResolvedValue({ data: initialVariables });

    const { result } = renderHook(() => useGetGlobalVariables(), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.data).toEqual(initialVariables));
    // Track isFetching before the refresh so React Query notifies this
    // observer when only the fetch status changes.
    expect(result.current.isFetching).toBe(false);
    mockApiGet.mockReset();
    mockApiGet.mockImplementationOnce(() => refreshRequest.promise);
    focusManager.setFocused(true);

    act(() => {
      void queryClient.refetchQueries({
        queryKey: getGlobalVariablesQueryKey({}),
        exact: true,
      });
    });
    await waitFor(() => expect(mockApiGet).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toEqual(initialVariables);

    await act(async () => refreshRequest.resolve({ data: refreshedVariables }));
    await waitFor(() =>
      expect(result.current.data).toEqual(refreshedVariables),
    );
    focusManager.setFocused(false);
    queryClient.clear();
  });

  it("refreshes the mirrored store when a later plain observer owns the query function", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const initialVariables = [
      variable("initial-id", "INITIAL_KEY", "Initial Field"),
    ];
    const refreshedVariables = [
      variable("refreshed-id", "REFRESHED_KEY", "Refreshed Field"),
    ];
    mockApiGet
      .mockResolvedValueOnce({ data: initialVariables })
      .mockResolvedValueOnce({ data: refreshedVariables });

    renderHook(
      () => {
        useGetGlobalVariables({ mirrorToStore: true });
        useGetGlobalVariables();
      },
      { wrapper: makeWrapper(queryClient) },
    );

    await waitFor(() =>
      expect(useGlobalVariablesStore.getState().globalVariablesEntries).toEqual(
        ["INITIAL_KEY"],
      ),
    );

    await act(async () => {
      await queryClient.refetchQueries({
        queryKey: getGlobalVariablesQueryKey({}),
        exact: true,
      });
    });

    await waitFor(() =>
      expect(useGlobalVariablesStore.getState().globalVariablesEntries).toEqual(
        ["REFRESHED_KEY"],
      ),
    );
    expect(mockApiGet).toHaveBeenCalledTimes(2);
    queryClient.clear();
  });
});

interface ScopeProps {
  flowId?: string;
  mirrorToStore: boolean;
}
