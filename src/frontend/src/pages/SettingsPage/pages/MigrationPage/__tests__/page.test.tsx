import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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
): MigrationState => ({
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: true },
  },
  record: { target: {}, steps: {}, accepted_findings: [] },
  steps: Object.entries(steps).map(([id, [state, reason]]) => ({
    id,
    state,
    reason,
  })) as MigrationStepState[],
  blocking_findings: [],
  acceptable_checks: [],
});

/** Opens the page on a state the server would send. Fresh for ever, so the page never asks a server for another. */
function open(migration: MigrationState) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Number.POSITIVE_INFINITY } },
  });
  client.setQueryData(migrationKeys.all, migration);
  useAuthStore.setState({ userData: { is_superuser: true } as Users });
  useUtilityStore.setState({ featureFlags: { instance_migration: true } });
  render(
    <QueryClientProvider client={client}>
      <MigrationPage />
    </QueryClientProvider>,
  );
}

const row = (id: MigrationStepState["id"]) =>
  within(screen.getByTestId(`migration-step-${id}`));

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
});
