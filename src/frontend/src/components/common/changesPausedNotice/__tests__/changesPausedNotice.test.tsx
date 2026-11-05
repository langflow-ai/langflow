import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "@/controllers/API/api";
import { migrationKeys } from "@/controllers/API/queries/migration";
import { useUtilityStore } from "@/stores/utilityStore";
import { axe } from "@/utils/a11y-test";
import { ChangesPausedNotice } from "..";

jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));

const clients: QueryClient[] = [];
afterEach(() => {
  clients.forEach((client) => client.clear());
  clients.length = 0;
  jest.clearAllMocks();
});

const externalRefusal = {
  isAxiosError: true,
  response: {
    status: 503,
    data: {
      detail: {
        code: "external_auth_maintenance",
        message: "External authentication paused",
      },
    },
  },
};

/** Shows the notice on what the server would answer. Fresh for ever, so it never asks a server for another. */
function showWith(
  paused: boolean | undefined,
  migrationOn = true,
  page = "/flows",
  maintenance = false,
  migration = !maintenance,
  externalAuthenticationPaused = false,
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { staleTime: Number.POSITIVE_INFINITY, retry: false },
    },
  });
  clients.push(client);
  if (paused !== undefined)
    client.setQueryData(migrationKeys.pause, {
      paused,
      maintenance,
      migration,
      externalAuthenticationPaused,
    });
  useUtilityStore.setState({
    featureFlags: { instance_migration: migrationOn },
  });
  render(
    <MemoryRouter initialEntries={[page]}>
      <QueryClientProvider client={client}>
        <ChangesPausedNotice />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return client;
}

describe("ChangesPausedNotice", () => {
  it("tells every signed-in user, on every page, that changes are paused", () => {
    showWith(true);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Changes are paused on this instance while it moves to a new one. You can look at your work, but changes you make now are not saved.",
    );
  });

  it("says nothing while changes go through", () => {
    showWith(false);

    // The region stays, so the pause is announced when it starts.
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("leaves the migration page to its own banner", () => {
    showWith(true, true, "/settings/migration");

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("shows database maintenance when instance migration is turned off", () => {
    showWith(true, false, "/flows", true);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Ordinary changes and flow runs are paused for maintenance. Administrators can still make changes.",
    );
  });

  it("shows database maintenance on the migration page too", () => {
    showWith(true, true, "/settings/migration", true);
    expect(screen.getByRole("status")).toHaveTextContent(
      "paused for maintenance",
    );
  });

  it("keeps the same live region when maintenance starts on the migration page", async () => {
    const client = showWith(false, true, "/settings/migration", false, false);
    const region = screen.getByRole("status");
    expect(region).toBeEmptyDOMElement();

    act(() => {
      client.setQueryData(migrationKeys.pause, {
        paused: true,
        maintenance: true,
        migration: false,
      });
    });

    expect(screen.getByRole("status")).toBe(region);
    await waitFor(() =>
      expect(region).toHaveTextContent("paused for maintenance"),
    );
  });

  it("shows the file migration restriction when both pauses are active", () => {
    showWith(true, true, "/flows", true, true);

    expect(screen.getByRole("status")).toHaveTextContent(
      "while it moves to a new one",
    );
    expect(screen.getByRole("status")).not.toHaveTextContent(
      "Administrators can still make changes",
    );
  });

  it("shows the specific external SSO refusal before status data has loaded", async () => {
    jest.mocked(api.get).mockRejectedValue(externalRefusal);
    showWith(undefined);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "External SSO sign-in is paused",
      ),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Use an API key or local JWT",
    );
  });

  it("replaces stale status with the SSO refusal and clears it after unfreeze", async () => {
    const client = showWith(false);
    const region = screen.getByRole("status");
    jest.mocked(api.get).mockRejectedValue(externalRefusal);
    await act(async () => {
      await client.invalidateQueries({ queryKey: migrationKeys.pause });
    });

    await waitFor(() =>
      expect(region).toHaveTextContent("External SSO sign-in is paused"),
    );
    expect(client.getQueryData(migrationKeys.pause)).toEqual({
      paused: true,
      maintenance: true,
      externalAuthenticationPaused: true,
    });
    jest.mocked(api.get).mockResolvedValue({
      data: { paused: false, maintenance: false, migration: false },
    });
    await act(async () => {
      await client.invalidateQueries({ queryKey: migrationKeys.pause });
    });

    expect(screen.getByRole("status")).toBe(region);
    await waitFor(() => expect(region).toBeEmptyDOMElement());
  });

  it.each([
    new Error("offline"),
    { isAxiosError: true, response: undefined },
    { isAxiosError: true, response: { status: 503, data: null } },
    {
      isAxiosError: true,
      response: {
        status: 503,
        data: { detail: { code: "auth_backend_unavailable" } },
      },
    },
    {
      isAxiosError: true,
      response: {
        status: 500,
        data: { detail: { code: "external_auth_maintenance" } },
      },
    },
    {
      isAxiosError: true,
      response: {
        status: 503,
        data: { detail: "External authentication paused" },
      },
    },
  ])(
    "preserves unrelated status failures without claiming an SSO maintenance refusal",
    async (error) => {
      const client = showWith(false);
      jest.mocked(api.get).mockRejectedValue(error);
      await act(async () => {
        await client.invalidateQueries({ queryKey: migrationKeys.pause });
      });

      expect(client.getQueryState(migrationKeys.pause)?.error).toBe(error);
      expect(screen.getByRole("status")).toBeEmptyDOMElement();
    },
  );

  it.each([
    [false, false, false],
    [true, true, false],
    [true, true, true],
  ])(
    "has no axe violations for the empty and maintenance live region states",
    async (paused, maintenance, external) => {
      showWith(
        paused,
        true,
        "/settings/migration",
        maintenance,
        false,
        external,
      );

      expect(await axe(document.body)).toHaveNoViolations();
    },
  );
});
