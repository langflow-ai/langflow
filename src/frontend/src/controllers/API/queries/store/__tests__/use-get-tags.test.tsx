/**
 * The Langflow Store tags query must not run when the store is off.
 *
 * `AppInitPage` calls `useGetTagsQuery` on every app boot, on every route, with no
 * regard for `ENABLE_LANGFLOW_STORE`. The backend proxies it to a third-party host,
 * so when `api.langflow.store` started serving a certificate for a different
 * hostname every page load produced a 500 — and the Playwright fixture, which fails
 * any test that sees an unexpected server error, took the whole suite down with it.
 *
 * The store's only consumer (`ShareModal`) already gates itself on `hasStore`, which
 * is `ENABLE_LANGFLOW_STORE && ...`, so nothing reads these tags while the flag is
 * off. The request was pure cost and pure risk.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useGetTagsQuery } from "../use-get-tags";

const mockGet = jest.fn();
jest.mock("../../../api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));
jest.mock("../../../helpers/constants", () => ({
  getURL: () => "/api/v1/store",
}));
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector({ setTags: jest.fn() }),
}));

let storeEnabled = false;
jest.mock("@/customization/feature-flags", () => ({
  get ENABLE_LANGFLOW_STORE() {
    return storeEnabled;
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function renderTagsQuery() {
  return renderHook(() => useGetTagsQuery({ enabled: true }), { wrapper });
}

describe("useGetTagsQuery — store outage must not reach the app", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue({ data: [] });
  });

  it("should_not_request_tags_when_the_store_is_disabled", async () => {
    storeEnabled = false;

    renderTagsQuery();

    await waitFor(() => {
      expect(mockGet).not.toHaveBeenCalled();
    });
  });

  it("should_request_tags_when_the_store_is_enabled", async () => {
    storeEnabled = true;

    renderTagsQuery();

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/v1/store/tags");
    });
  });

  it("should_keep_honouring_an_explicit_disabled_option", async () => {
    storeEnabled = true;

    renderHook(() => useGetTagsQuery({ enabled: false }), { wrapper });

    await waitFor(() => {
      expect(mockGet).not.toHaveBeenCalled();
    });
  });
});
