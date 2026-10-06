import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { api } from "@/controllers/API/api";
import {
  type MigrationState,
  type MigrationStepState,
  migrationKeys,
} from "@/controllers/API/queries/migration";
import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { Users } from "@/types/api";
import MigrationPage from "../index";

const state = (
  steps: Partial<Record<MigrationStepState["id"], [string, string?]>>,
  record: Partial<MigrationState["record"]> = {},
): MigrationState => ({
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: true },
    secret_key: { source: "env" },
  },
  record: { target: {}, steps: {}, accepted_findings: [], ...record },
  steps: Object.entries(steps).map(([id, [state, reason]]) => ({
    id,
    state,
    reason,
  })) as MigrationStepState[],
  blocking_findings: [],
  acceptable_findings: [],
});

/** Opens the page on a state the server would send. Fresh for ever, so the page never asks a server for another. */
function open(migration: MigrationState) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Number.POSITIVE_INFINITY } },
  });
  client.setQueryData(migrationKeys.all, migration);
  useAuthStore.setState({ userData: { is_superuser: true } as Users });
  useUtilityStore.setState({ featureFlags: { instance_migration: true } });
  const { unmount } = render(
    <QueryClientProvider client={client}>
      <MigrationPage />
    </QueryClientProvider>,
  );
  return { client, unmount };
}

const row = (id: MigrationStepState["id"]) =>
  within(screen.getByTestId(`migration-step-${id}`));

afterEach(() => jest.restoreAllMocks());

describe("the steps after the check", () => {
  it("offers a step only when the server can do it", () => {
    open(
      state({
        check_source: ["done"],
        connect_target: ["current", "not_available"],
      }),
    );

    expect(row("connect_target").getByText("Coming soon")).toBeInTheDocument();
    expect(row("connect_target").queryByRole("button")).not.toBeInTheDocument();
    // A step the admin has not reached says nothing of the kind.
    expect(
      row("secret_key").queryByText("Coming soon"),
    ).not.toBeInTheDocument();
  });

  it("says the same of a step this page has no form for yet, whatever the server can do", () => {
    open(
      state({
        check_source: ["done"],
        connect_target: ["done"],
        secret_key: ["done"],
        pause: ["done"],
        backup: ["done"],
        copy_database: ["current"],
      }),
    );

    expect(row("copy_database").getByText("Coming soon")).toBeInTheDocument();
  });

  it("opens the step the admin is on, and holds no form for one they haven't reached", () => {
    const { unmount } = open(
      state({ check_source: ["done"], connect_target: ["current"] }),
    );
    expect(
      row("connect_target").getByRole("button", { name: "Test and save" }),
    ).toBeVisible();
    unmount();

    open(state({ check_source: ["current"], connect_target: ["locked"] }));
    // Not hidden either: a locked step has nothing to fill in or to press.
    expect(
      row("connect_target").queryByRole("button", { hidden: true }),
    ).not.toBeInTheDocument();
  });

  it("sums up where the data goes once it is saved", () => {
    open(
      state(
        {
          check_source: ["done"],
          connect_target: ["done"],
          secret_key: ["current", "not_available"],
        },
        {
          destinations: {
            database: { location: "db.internal:5432/target" },
            vectors: { kind: "pgvector" },
            files: { bucket: "acme", prefix: "files" },
            saved_by: "alice",
            saved_at: "2026-10-06T12:00:00Z",
          },
        },
      ),
    );

    expect(
      row("connect_target").getByText(
        "Database: db.internal:5432/target · Knowledge bases: PostgreSQL · Files: acme",
      ),
    ).toBeInTheDocument();
  });

  it("keeps a saved step one click away, so a destination can change", async () => {
    open(
      state(
        {
          check_source: ["done"],
          connect_target: ["done"],
          secret_key: ["current", "not_available"],
        },
        {
          destinations: {
            saved_by: "alice",
            saved_at: "2026-10-06T12:00:00Z",
          },
        },
      ),
    );
    const change = row("connect_target").getByRole("button", {
      name: "Change or enter again",
      hidden: true,
    });
    expect(change).not.toBeVisible();

    await userEvent.click(
      row("connect_target").getByRole("button", {
        name: "Where your data goes",
      }),
    );

    expect(change).toBeVisible();
  });

  it("reads the record again when a request fails, since a step may have reopened meanwhile", async () => {
    jest
      .spyOn(api, "put")
      .mockRejectedValue(
        new AxiosError("Network Error", AxiosError.ERR_NETWORK),
      );
    // What the server would say next: the check has to run again.
    jest.spyOn(api, "get").mockResolvedValue({
      data: state({ check_source: ["current"], connect_target: ["locked"] }),
    });
    open(state({ check_source: ["done"], connect_target: ["current"] }));

    // Sent as it stands: what the form holds makes no difference to what follows a failure.
    fireEvent.submit(
      row("connect_target").getByRole("button", { name: "Test and save" }),
    );

    await waitFor(() =>
      expect(
        row("connect_target").queryByRole("button", { hidden: true }),
      ).not.toBeInTheDocument(),
    );
  });

  it("moves focus to the next step when one finishes", async () => {
    const { client } = open(
      state({ check_source: ["current"], connect_target: ["locked"] }),
    );
    const next = row("connect_target").getByRole("heading", {
      name: "Where your data goes",
    });
    expect(next).not.toHaveFocus();

    client.setQueryData(
      migrationKeys.all,
      state({ check_source: ["done"], connect_target: ["current"] }),
    );

    await waitFor(() => expect(next).toHaveFocus());
  });

  it("leaves focus where it is when the next step can't be done yet", async () => {
    const { client } = open(
      state({ check_source: ["current"], connect_target: ["locked"] }),
    );

    client.setQueryData(
      migrationKeys.all,
      state({
        check_source: ["done"],
        connect_target: ["current", "not_available"],
      }),
    );

    await waitFor(() =>
      expect(
        row("connect_target").getByText("Coming soon"),
      ).toBeInTheDocument(),
    );
    expect(document.body).toHaveFocus();
  });

  it("sums up the key once it is verified, and leaves nothing to open", () => {
    open(
      state(
        {
          check_source: ["done"],
          connect_target: ["done"],
          secret_key: ["done"],
          pause: ["current", "not_available"],
        },
        {
          secret_key: {
            verified_by: "alice",
            verified_at: "2026-10-06T12:05:00Z",
          },
        },
      ),
    );

    expect(
      row("secret_key").getByText(/^Verified .* by alice\.$/),
    ).toBeInTheDocument();
    expect(row("secret_key").queryByRole("button")).not.toBeInTheDocument();
  });
});
