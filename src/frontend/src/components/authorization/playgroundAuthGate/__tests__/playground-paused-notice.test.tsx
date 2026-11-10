import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { SessionResponse } from "@/controllers/API/queries/auth";
import { migrationKeys } from "@/controllers/API/queries/migration";
import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { PlaygroundAuthGate } from "..";

const mockGet = jest.fn();
let mockSession: SessionResponse;

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));
jest.mock("@/controllers/API/queries/auth", () => ({
  useGetAuthSession: () => ({ data: mockSession, isFetched: true }),
  useGetAutoLogin: () => ({ isFetched: true }),
}));
jest.mock("@/pages/LoadingPage", () => ({
  LoadingPage: () => <div data-testid="loading" />,
}));

let client: QueryClient;

beforeEach(() => {
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  useAuthStore.setState({ autoLogin: false, isAuthenticated: false });
  useUtilityStore.setState({ featureFlags: { instance_migration: true } });
  mockSession = {
    authenticated: true,
    user: {
      id: "viewer",
      username: "viewer",
      is_active: true,
      is_superuser: false,
    },
  };
  mockGet.mockReset().mockResolvedValue({ data: { paused: true } });
});

afterEach(() => client.clear());

function showPlayground() {
  render(
    <MemoryRouter initialEntries={["/playground/flow-id/"]}>
      <QueryClientProvider client={client}>
        <PlaygroundAuthGate>
          <main>Playground</main>
        </PlaygroundAuthGate>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

it("shows a signed-in playground visitor the pause and clears it on resume", async () => {
  showPlayground();

  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent(
      "Changes are paused on this instance",
    ),
  );
  expect(mockGet).toHaveBeenCalledTimes(1);
  expect(mockGet.mock.calls[0][0]).toContain("/migration/pause");

  mockGet.mockResolvedValue({ data: { paused: false } });
  await act(async () => {
    await client.invalidateQueries({ queryKey: migrationKeys.pause });
  });
  await waitFor(() => expect(screen.getByRole("status")).toBeEmptyDOMElement());
});

it("does not ask the signed-in-only pause endpoint for anonymous visitors", () => {
  mockSession = { authenticated: false };
  showPlayground();

  expect(screen.getByRole("main")).toHaveTextContent("Playground");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(mockGet).not.toHaveBeenCalled();
  expect(client.getQueryState(migrationKeys.pause)).toBeUndefined();
});

it("does not fetch or show a notice when migration is disabled", () => {
  useUtilityStore.setState({ featureFlags: { instance_migration: false } });
  showPlayground();

  expect(screen.getByRole("main")).toHaveTextContent("Playground");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(mockGet).not.toHaveBeenCalled();
});
