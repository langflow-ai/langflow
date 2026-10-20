import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { RevisionPage } from "@/types/flow/revision";

const apiGetMock = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => apiGetMock(...args) },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

import { historyChanged, useGetFlowRevisions } from "../use-get-flow-revisions";

const page = (
  latest: number,
  overrides: Partial<RevisionPage> = {},
): RevisionPage => ({
  flow_id: "flow-1",
  latest_revision: latest,
  current_revision: latest,
  earliest_revision: 1,
  entries: [],
  next_before: null,
  ...overrides,
});

type Params = { limit: number; include?: string; before?: number };

/** The server's history, newest revision `latest`; counts each kind of request. */
function serve(history: { latest: number }) {
  const calls = { full: 0, newest: 0 };
  apiGetMock.mockImplementation(
    (_url: string, { params }: { params: Params }) => {
      if (params.include === "operations") calls.full += 1;
      else calls.newest += 1;
      return Promise.resolve({ data: page(history.latest) });
    },
  );
  return calls;
}

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useGetFlowRevisions", () => {
  beforeEach(() => apiGetMock.mockReset());

  // The defect: the poll reloaded every loaded entry, with its operations,
  // every ten seconds.
  it("polls only the newest entry, without operations, while nothing changes", async () => {
    const calls = serve({ latest: 5 });
    renderHook(() => useGetFlowRevisions("flow-1", { pollInterval: 20 }), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(calls.newest).toBeGreaterThanOrEqual(4));
    expect(calls.full).toBe(1);
    expect(apiGetMock).toHaveBeenCalledWith("/api/v1/flows/flow-1/revisions", {
      params: { limit: 1 },
    });
  });

  it("loads the pages again when the history changed", async () => {
    const history = { latest: 5 };
    const calls = serve(history);
    const { result } = renderHook(
      () => useGetFlowRevisions("flow-1", { pollInterval: 20 }),
      { wrapper: wrapper() },
    );
    await waitFor(() =>
      expect(result.current.data?.pages[0].latest_revision).toBe(5),
    );

    history.latest = 6;

    await waitFor(() =>
      expect(result.current.data?.pages[0].latest_revision).toBe(6),
    );
    expect(calls.full).toBe(2);
  });

  it("does not poll without an interval", async () => {
    const calls = serve({ latest: 5 });
    const { result } = renderHook(() => useGetFlowRevisions("flow-1"), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(calls.newest).toBe(0);
  });
});

describe("historyChanged", () => {
  it("sees new revisions and compaction", () => {
    expect(historyChanged(page(5), page(5))).toBe(false);
    expect(historyChanged(page(5), page(6))).toBe(true);
    expect(historyChanged(page(5), page(5, { earliest_revision: 3 }))).toBe(
      true,
    );
  });
});
