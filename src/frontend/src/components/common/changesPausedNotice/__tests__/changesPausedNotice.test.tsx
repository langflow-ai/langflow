import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { migrationKeys } from "@/controllers/API/queries/migration";
import { useUtilityStore } from "@/stores/utilityStore";
import { ChangesPausedNotice } from "..";

/** Shows the notice on what the server would answer. Fresh for ever, so it never asks a server for another. */
function showWith(
  paused: boolean | undefined,
  migrationOn = true,
  page = "/flows",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Number.POSITIVE_INFINITY } },
  });
  if (paused !== undefined)
    client.setQueryData(migrationKeys.pause, { paused });
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

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("asks the server nothing when the migration is turned off", () => {
    const client = showWith(undefined, false);

    expect(client.getQueryState(migrationKeys.pause)?.fetchStatus).not.toBe(
      "fetching",
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
