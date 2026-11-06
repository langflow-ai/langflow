import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { useBulkDeleteSessions } from "../use-bulk-delete-sessions";

const mockDelete = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { delete: (...args: unknown[]) => mockDelete(...args) },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));

it("deletes more sessions than one request accepts in batches of 500", async () => {
  mockDelete.mockResolvedValue({ data: null });
  const client = new QueryClient();
  const { result } = renderHook(() => useBulkDeleteSessions(), {
    wrapper: ({ children }: PropsWithChildren) =>
      createElement(QueryClientProvider, { client }, children),
  });
  const sessionIds = Array.from({ length: 1001 }, (_, i) => `session-${i}`);

  await act(() => result.current.mutateAsync({ sessionIds }));

  expect(mockDelete.mock.calls.map(([, config]) => config.data.length)).toEqual(
    [500, 500, 1],
  );
  expect(mockDelete.mock.calls.flatMap(([, config]) => config.data)).toEqual(
    sessionIds,
  );
});
