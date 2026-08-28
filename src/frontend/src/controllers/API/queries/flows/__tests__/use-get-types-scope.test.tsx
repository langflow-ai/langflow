import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useTypesStore } from "@/stores/typesStore";

const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/all",
}));

jest.mock("@/stores/flowStore", () => ({
  recomputeComponentsToUpdateIfNeeded: jest.fn(),
  syncNodeTranslations: jest.fn(),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { setIsLoading: jest.Mock }) => unknown) =>
    selector({ setIsLoading: jest.fn() }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  extractSecretFieldsFromComponents: (data: Record<string, unknown>) =>
    new Set(Object.keys(data)),
  templatesGenerator: (data: Record<string, unknown>) => data,
  typesGenerator: (data: Record<string, unknown>) =>
    Object.fromEntries(
      Object.keys(data).map((category) => [category, category]),
    ),
}));

import { useGetTypes } from "../use-get-types";

const palette = (category: string, component: string) => ({
  [category]: {
    [component]: {
      description: component,
      display_name: component,
      documentation: "",
      template: {},
    },
  },
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
};

const expectPaletteStoreToBeEmpty = () => {
  const state = useTypesStore.getState();
  expect(state.data).toEqual({});
  expect(state.types).toEqual({});
  expect(state.templates).toEqual({});
  expect(state.ComponentFields).toEqual(new Set());
  expect(state.componentDisplayNames).toEqual({});
};

const makeWrapper = (queryClient: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

describe("useGetTypes scoped store ownership", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    jest.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    onlineManager.setOnline(true);
    useTypesStore.setState({
      activeScopeKey: null,
      types: {},
      templates: {},
      data: {},
      ComponentFields: new Set(),
      componentDisplayNames: {},
    });
  });

  afterEach(() => {
    onlineManager.setOnline(undefined);
    queryClient.clear();
  });

  it("replaces narrower scope data and reinstalls cached A on A to B to A", async () => {
    const flowA = palette("provider_a", "AComponent");
    const flowB = palette("provider_b", "BComponent");
    mockApiGet.mockImplementation((url: string) => {
      if (url.includes("flow_id=flow-a"))
        return Promise.resolve({ data: flowA });
      if (url.includes("flow_id=flow-b"))
        return Promise.resolve({ data: flowB });
      throw new Error(`unexpected URL: ${url}`);
    });

    const { rerender } = renderHook(({ flowId }) => useGetTypes({ flowId }), {
      initialProps: { flowId: "flow-a" },
      wrapper: makeWrapper(queryClient),
    });

    await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowA));
    rerender({ flowId: "flow-b" });
    await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowB));
    expect(useTypesStore.getState().data).not.toHaveProperty("provider_a");

    rerender({ flowId: "flow-a" });
    await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowA));
    expect(useTypesStore.getState().data).not.toHaveProperty("provider_b");
    expect(
      mockApiGet.mock.calls.filter(([url]) =>
        String(url).includes("flow_id=flow-a"),
      ),
    ).toHaveLength(1);
  });

  it("does not let an obsolete request replace the active scope", async () => {
    const flowA = palette("provider_a", "AComponent");
    const flowB = palette("provider_b", "BComponent");
    const a = deferred<{ data: typeof flowA }>();
    const b = deferred<{ data: typeof flowB }>();
    mockApiGet.mockImplementation((url: string) =>
      url.includes("flow_id=flow-a") ? a.promise : b.promise,
    );

    const { rerender } = renderHook(({ flowId }) => useGetTypes({ flowId }), {
      initialProps: { flowId: "flow-a" },
      wrapper: makeWrapper(queryClient),
    });
    rerender({ flowId: "flow-b" });

    await act(async () => b.resolve({ data: flowB }));
    await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowB));
    await act(async () => a.resolve({ data: flowA }));
    await waitFor(() =>
      expect(
        queryClient.getQueryData(["useGetTypes", "flow-a", undefined]),
      ).toEqual(flowA),
    );
    expect(useTypesStore.getState().data).toEqual(flowB);
  });

  it("restores the active store after an equal scoped palette refetch", async () => {
    const dateNow = jest.spyOn(Date, "now").mockReturnValue(1_000_000);
    const flowA = palette("provider_a", "AComponent");
    const initialDisplayNames = {
      acomponent: {
        display_name: ["A Component"],
        description: ["Initial description"],
      },
    };
    const refreshedDisplayNames = {
      acomponent: {
        display_name: ["Localized A Component"],
        description: ["Localized description"],
      },
    };
    mockApiGet
      .mockResolvedValueOnce({
        data: {
          ...flowA,
          component_display_names: initialDisplayNames,
        },
      })
      .mockResolvedValueOnce({
        data: {
          ...flowA,
          component_display_names: refreshedDisplayNames,
        },
      });

    try {
      renderHook(() => useGetTypes({ flowId: "flow-a" }), {
        wrapper: makeWrapper(queryClient),
      });

      await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowA));
      expect(useTypesStore.getState().componentDisplayNames).toEqual(
        initialDisplayNames,
      );

      act(() => useTypesStore.getState().setTypes({}));
      expect(useTypesStore.getState().data).toEqual({});

      await act(async () => {
        await queryClient.invalidateQueries({
          queryKey: ["useGetTypes", "flow-a", undefined],
          exact: true,
        });
      });

      await waitFor(() => expect(useTypesStore.getState().data).toEqual(flowA));
      expect(useTypesStore.getState().componentDisplayNames).toEqual(
        refreshedDisplayNames,
      );
      expect(mockApiGet).toHaveBeenCalledTimes(2);
    } finally {
      dateNow.mockRestore();
    }
  });

  it("preserves a stale scoped palette while refreshing provider revocation", async () => {
    const now = 1_000_000;
    const dateNow = jest.spyOn(Date, "now").mockReturnValue(now);
    const allowed = palette("openai", "OpenAIComponent");
    const revoked = palette("core", "PromptComponent");
    const refresh = deferred<{ data: typeof revoked }>();
    mockApiGet
      .mockResolvedValueOnce({ data: allowed })
      .mockImplementationOnce(() => refresh.promise);

    try {
      renderHook(() => useGetTypes({ flowId: "flow-a" }), {
        wrapper: makeWrapper(queryClient),
      });

      await waitFor(() =>
        expect(useTypesStore.getState().data).toEqual(allowed),
      );

      dateNow.mockReturnValue(now + 60_001);
      act(() => focusManager.setFocused(false));
      act(() => focusManager.setFocused(true));

      await waitFor(() =>
        expect(
          queryClient.getQueryState(["useGetTypes", "flow-a", undefined])
            ?.fetchStatus,
        ).toBe("fetching"),
      );
      expect(useTypesStore.getState().data).toEqual(allowed);

      await act(async () => refresh.resolve({ data: revoked }));
      await waitFor(() =>
        expect(useTypesStore.getState().data).toEqual(revoked),
      );
      expect(mockApiGet).toHaveBeenCalledTimes(2);
    } finally {
      focusManager.setFocused(undefined);
      dateNow.mockRestore();
    }
  });

  it("preserves a cached scoped palette while an offline refresh is paused", async () => {
    const allowed = palette("openai", "OpenAIComponent");
    mockApiGet.mockResolvedValue({ data: allowed });

    renderHook(() => useGetTypes({ flowId: "flow-a" }), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(useTypesStore.getState().data).toEqual(allowed));

    act(() => onlineManager.setOnline(false));
    act(() => {
      void queryClient.invalidateQueries({
        queryKey: ["useGetTypes", "flow-a", undefined],
        exact: true,
      });
    });

    await waitFor(() =>
      expect(
        queryClient.getQueryState(["useGetTypes", "flow-a", undefined])
          ?.fetchStatus,
      ).toBe("paused"),
    );
    expect(useTypesStore.getState().data).toEqual(allowed);

    onlineManager.setOnline(true);
  });

  it("clears a scoped palette when a project move resets its flow cache", async () => {
    const projectA = palette("provider_a", "AComponent");
    const projectB = deferred<{ data: ReturnType<typeof palette> }>();
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockApiGet
      .mockResolvedValueOnce({
        data: {
          ...projectA,
          component_display_names: {
            acomponent: {
              display_name: ["A Component"],
              description: ["Project A"],
            },
          },
        },
      })
      .mockImplementationOnce(() => projectB.promise);

    try {
      renderHook(() => useGetTypes({ flowId: "flow-a", retry: false }), {
        wrapper: makeWrapper(queryClient),
      });

      await waitFor(() =>
        expect(useTypesStore.getState().data).toEqual(projectA),
      );
      expect(useTypesStore.getState().ComponentFields).toEqual(
        new Set(["provider_a"]),
      );
      expect(useTypesStore.getState().componentDisplayNames).not.toEqual({});

      act(() => {
        void queryClient.resetQueries({
          queryKey: ["useGetTypes", "flow-a", undefined],
          exact: true,
        });
      });

      await waitFor(() =>
        expect(
          queryClient.getQueryState(["useGetTypes", "flow-a", undefined])
            ?.fetchStatus,
        ).toBe("fetching"),
      );
      expectPaletteStoreToBeEmpty();

      await act(async () => projectB.reject(new Error("project B denied")));
      await waitFor(() =>
        expect(
          queryClient.getQueryState(["useGetTypes", "flow-a", undefined])
            ?.status,
        ).toBe("error"),
      );
      expectPaletteStoreToBeEmpty();
    } finally {
      errorSpy.mockRestore();
    }
  });

  it("preserves the unscoped palette during a background refresh failure", async () => {
    const globalPalette = palette("global_provider", "GlobalComponent");
    const refresh = deferred<{ data: ReturnType<typeof palette> }>();
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockApiGet
      .mockResolvedValueOnce({ data: globalPalette })
      .mockImplementationOnce(() => refresh.promise);

    try {
      renderHook(() => useGetTypes({ retry: false }), {
        wrapper: makeWrapper(queryClient),
      });

      await waitFor(() =>
        expect(useTypesStore.getState().data).toEqual(globalPalette),
      );

      void queryClient.invalidateQueries({
        queryKey: ["useGetTypes", undefined, undefined],
        exact: true,
      });
      await waitFor(() =>
        expect(
          queryClient.getQueryState(["useGetTypes", undefined, undefined])
            ?.fetchStatus,
        ).toBe("fetching"),
      );
      expect(useTypesStore.getState().data).toEqual(globalPalette);

      await act(async () => refresh.reject(new Error("refresh failed")));
      await waitFor(() =>
        expect(
          queryClient.getQueryState(["useGetTypes", undefined, undefined])
            ?.status,
        ).toBe("error"),
      );
      expect(useTypesStore.getState().data).toEqual(globalPalette);
    } finally {
      errorSpy.mockRestore();
    }
  });
});
