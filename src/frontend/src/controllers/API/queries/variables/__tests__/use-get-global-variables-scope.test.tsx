import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

import { useGetGlobalVariables } from "../use-get-global-variables";

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
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
};

const makeWrapper = (queryClient: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

describe("useGetGlobalVariables store isolation", () => {
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
    useAuthStore.setState({ isAuthenticated: true });
    useGlobalVariablesStore.setState({
      globalVariablesEntries: undefined,
      globalVariablesEntities: undefined,
      unavailableFields: {},
    });

    renderHook(
      () => {
        useGetGlobalVariables({ mirrorToStore: true } as never);
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
});
