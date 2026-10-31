import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { connectionsKeys } from "../keys";
import type { ConnectionRead } from "../types";
import { usePendingConnectionPoll } from "../use-connections";

const mockGetConnection = jest.fn();

jest.mock("../api", () => ({
  getConnection: (...args: unknown[]) => mockGetConnection(...args),
}));

const CREATED_AT = "2026-09-18T10:00:00Z";
const CONSENTED_AT = "2026-09-18T10:00:30Z";

const row = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: "c1",
  owner_id: "u1",
  ownership_mode: "user",
  provider_key: "google",
  name: "work",
  display_name: "Work",
  status: "pending",
  status_reason: null,
  health: "unknown",
  granted_scopes: [],
  executing_identity: { identity: "user_delegated" },
  allow_non_interactive: false,
  has_credentials: false,
  health_checked_at: null,
  created_at: CREATED_AT,
  updated_at: CREATED_AT,
  ...overrides,
});

// The page's cache right after create: the list holds the row as pending.
const seededClient = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(connectionsKeys.list(), [row()]);
  client.setQueryData(connectionsKeys.integrations(), { providers: [] });
  return client;
};

const wrapperFor =
  (client: QueryClient) =>
  ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);

const baseline = { id: "c1", updatedAt: CREATED_AT };

describe("usePendingConnectionPoll", () => {
  beforeEach(() => mockGetConnection.mockReset());

  it("refreshes the connections list once consent lands", async () => {
    // Consent completes in another window, outside every mutation that would
    // refresh the cache, and a popup closing never hides this tab, so the
    // visibility-driven focus refetch does not fire either. Without this the
    // list kept showing "Not ready / not signed in" until a manual reload.
    mockGetConnection.mockResolvedValue(
      row({ status: "ready", has_credentials: true, updated_at: CONSENTED_AT }),
    );
    const client = seededClient();
    const invalidate = jest.spyOn(client, "invalidateQueries");

    renderHook(() => usePendingConnectionPoll(baseline, { intervalMs: 10 }), {
      wrapper: wrapperFor(client),
    });

    await waitFor(() =>
      expect(client.getQueryState(connectionsKeys.list())?.isInvalidated).toBe(
        true,
      ),
    );
    // connection_count on the provider catalog moves with it.
    expect(
      client.getQueryState(connectionsKeys.integrations())?.isInvalidated,
    ).toBe(true);

    // `all` includes this poll's own entry, so the invalidation refetches it
    // once. That refetch must not invalidate again.
    await waitFor(() =>
      expect(mockGetConnection.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(invalidate).toHaveBeenCalledTimes(1);
  });

  it("leaves the list alone while consent is still pending", async () => {
    mockGetConnection.mockResolvedValue(row());
    const client = seededClient();

    renderHook(() => usePendingConnectionPoll(baseline, { intervalMs: 10 }), {
      wrapper: wrapperFor(client),
    });

    await waitFor(() =>
      expect(mockGetConnection.mock.calls.length).toBeGreaterThanOrEqual(3),
    );
    expect(client.getQueryState(connectionsKeys.list())?.isInvalidated).toBe(
      false,
    );
  });
});
