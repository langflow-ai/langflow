import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/models",
}));

import { useGetProviderVariables } from "../use-get-provider-variables";

const makeWrapper = (queryClient: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

describe("useGetProviderVariables", () => {
  it("removes revoked provider descriptors from a mounted flow on stale focus", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const dateNow = jest.spyOn(Date, "now").mockReturnValue(1_000_000);
    mockApiGet
      .mockResolvedValueOnce({
        data: {
          OpenAI: [
            {
              variable_name: "API Key",
              variable_key: "OPENAI_API_KEY",
              required: true,
              is_secret: true,
              is_list: false,
              options: [],
            },
          ],
        },
      })
      .mockResolvedValueOnce({ data: {} });

    try {
      const { result } = renderHook(
        () => useGetProviderVariables({ flowId: "flow-one" }),
        { wrapper: makeWrapper(queryClient) },
      );

      await waitFor(() =>
        expect(Object.keys(result.current.data ?? {})).toEqual(["OpenAI"]),
      );
      expect(mockApiGet).toHaveBeenLastCalledWith(
        "/api/v1/models/provider-variable-mapping?flow_id=flow-one",
      );

      dateNow.mockReturnValue(1_030_001);
      act(() => focusManager.setFocused(false));
      act(() => focusManager.setFocused(true));

      await waitFor(() => expect(result.current.data).toEqual({}));
      expect(mockApiGet).toHaveBeenCalledTimes(2);
    } finally {
      focusManager.setFocused(undefined);
      dateNow.mockRestore();
      queryClient.clear();
    }
  });
});
