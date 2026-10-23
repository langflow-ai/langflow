import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { makeEvent } from "@/components/core/triggers/__tests__/fixtures";
import { listTriggerEvents } from "../api";
import { useTriggerEventsQuery } from "../use-triggers";

jest.mock("../api", () => ({ listTriggerEvents: jest.fn() }));
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector({ triggerPollingInterval: 0 }),
}));

const wrapper = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
};

beforeEach(() => jest.resetAllMocks());

it("loads more than 200 events using bounded offset pages", async () => {
  const events = Array.from({ length: 220 }, (_, id) =>
    makeEvent({ id: String(id) }),
  );
  jest
    .mocked(listTriggerEvents)
    .mockImplementation(async (_id, options = {}) =>
      events.slice(
        options.offset ?? 0,
        (options.offset ?? 0) + (options.limit ?? 50),
      ),
    );
  const { result } = renderHook(() => useTriggerEventsQuery("first"), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(result.current.data).toHaveLength(50));
  for (let page = 1; page <= 4; page++) {
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() =>
      expect(result.current.data).toHaveLength(Math.min((page + 1) * 50, 220)),
    );
  }
  expect(result.current.data).toHaveLength(220);
  expect(result.current.hasNextPage).toBe(false);
  expect(listTriggerEvents).toHaveBeenLastCalledWith("first", {
    limit: 51,
    offset: 200,
  });
});

it("retains loaded rows while fetching older events and clears them for another trigger", async () => {
  let finish: (rows: ReturnType<typeof makeEvent>[]) => void = () => {};
  jest
    .mocked(listTriggerEvents)
    .mockResolvedValueOnce(
      Array.from({ length: 51 }, (_, id) => makeEvent({ id: String(id) })),
    )
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockImplementationOnce(() => new Promise(() => {}));
  const { result, rerender } = renderHook(
    ({ id }) => useTriggerEventsQuery(id),
    {
      initialProps: { id: "first" },
      wrapper: wrapper(),
    },
  );
  await waitFor(() => expect(result.current.data).toHaveLength(50));
  act(() => {
    void result.current.fetchNextPage();
  });
  await waitFor(() => expect(result.current.isFetchingNextPage).toBe(true));
  expect(result.current.data).toHaveLength(50);
  expect(result.current.hasNextPage).toBe(true);
  await act(async () => {
    finish([makeEvent({ id: "older" })]);
  });
  rerender({ id: "second" });
  expect(result.current.data).toBeUndefined();
});
