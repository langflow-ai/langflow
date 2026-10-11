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
  type MigrationCopyRun,
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
  const { unmount } = render(
    <QueryClientProvider client={client}>
      <MigrationPage />
    </QueryClientProvider>,
  );
  return { client, unmount };
}

const row = (id: MigrationStepState["id"]) =>
  within(screen.getByTestId(`migration-step-${id}`));

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  jest.restoreAllMocks();
});

// Everything before the copies is done.
const copied: Parameters<typeof state>[0] = {
  check_source: ["done"],
  connect_target: ["done"],
  secret_key: ["done"],
  pause: ["done"],
  backup: ["done"],
};
const run = (status: MigrationCopyRun["status"]): MigrationCopyRun => ({
  run_id: "run-1",
  status,
  dry_run: false,
  started_by: "alice",
  started_at: "2026-10-06T12:05:00Z",
  finished_at: status === "running" ? null : "2026-10-06T12:06:00Z",
  report:
    status === "done"
      ? { ok: true, tables_copied: 1059, rows_copied: 12345 }
      : null,
  error: null,
});

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
    // A step the admin has not reached says nothing of the kind. It waits for the steps above it.
    expect(
      row("secret_key").queryByText("Coming soon"),
    ).not.toBeInTheDocument();
    expect(
      row("secret_key").getByText("Finish the steps above first."),
    ).toBeInTheDocument();
  });

  it("says the same of a step this page has no form for yet, whatever the server can do", () => {
    open(
      state({
        check_source: ["done"],
        connect_target: ["done"],
        secret_key: ["done"],
        pause: ["done"],
        backup: ["done"],
        copy_database: ["skipped"],
        copy_knowledge_bases: ["skipped"],
        copy_files: ["skipped"],
        start_target: ["current"],
      }),
    );

    expect(row("start_target").getByText("Coming soon")).toBeInTheDocument();
  });

  it("opens the step the admin is on, and holds no form for one they haven't reached", () => {
    const { unmount } = open(
      state({ check_source: ["done"], connect_target: ["current"] }),
    );
    expect(
      row("connect_target").getByRole("button", { name: "Test and save" }),
    ).toBeVisible();
    unmount();

    open(
      state({
        check_source: ["current"],
        connect_target: ["locked"],
        copy_database: ["locked"],
      }),
    );
    // Not hidden either: a locked step has nothing to fill in or to press.
    for (const id of ["connect_target", "copy_database"] as const) {
      expect(
        row(id).queryByRole("button", { hidden: true }),
      ).not.toBeInTheDocument();
    }
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

  it("shows the pause from the record, whatever the pause step still waits for", () => {
    open(
      state(
        {
          check_source: ["blocked", "blocking_findings"],
          connect_target: ["done"],
          secret_key: ["done"],
          pause: ["blocked", "recheck_failed"],
          backup: ["locked", "earlier_step"],
        },
        { pause: { frozen_at: "2026-10-06T12:00:00Z", frozen_by: "alice" } },
      ),
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Changes are paused on this instance.",
    );
    expect(row("pause").getByRole("alert")).toHaveTextContent(
      "Something changed before the pause.",
    );
    expect(
      row("backup").queryByRole("button", { hidden: true }),
    ).not.toBeInTheDocument();
  });

  it("shows the pause as working while the check runs again", () => {
    const check = (status: "running" | "cancelled") => ({
      steps: {
        check_source: {
          status,
          started_by: "alice",
          started_at: "2026-10-06T12:01:00Z",
          target_version: "1.13.0",
          exit_code: null,
          report: null,
          error: null,
        },
      },
      pause: { frozen_at: "2026-10-06T12:00:00Z", frozen_by: "alice" },
    });
    const steps: Parameters<typeof state>[0] = {
      check_source: ["current"],
      connect_target: ["done"],
      secret_key: ["done"],
      pause: ["blocked", "recheck_pending"],
    };
    const marker = () =>
      row("pause").getByRole("heading").parentElement?.previousElementSibling;

    const { unmount } = open(state(steps, check("running")));
    expect(marker()).not.toHaveClass("border-destructive");
    unmount();

    // The run stopped, so the pause waits on the admin again.
    open(state(steps, check("cancelled")));
    expect(marker()).toHaveClass("border-destructive");
  });

  it("sums up the pause once it is done, and leaves nothing to press in its row", () => {
    open(
      state(
        {
          check_source: ["done"],
          connect_target: ["done"],
          secret_key: ["done"],
          pause: ["done"],
          backup: ["current", "not_available"],
        },
        { pause: { frozen_at: "2026-10-06T12:00:00Z", frozen_by: "alice" } },
      ),
    );

    expect(
      row("pause").getByText(/^Paused .* by alice\.$/),
    ).toBeInTheDocument();
    // Turning changes back on belongs to the banner and to the way back.
    expect(row("pause").queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers the way back only when this server can pause", () => {
    const { unmount } = open(
      state({ check_source: ["done"], pause: ["current", "not_available"] }),
    );
    expect(
      screen.queryByText("If something goes wrong"),
    ).not.toBeInTheDocument();
    unmount();

    open(state({ check_source: ["done"], pause: ["locked", "earlier_step"] }));
    expect(screen.getByText("If something goes wrong")).toBeInTheDocument();
  });

  it("sums up the backup once it is confirmed, and leaves nothing to open", () => {
    open(
      state(
        {
          check_source: ["done"],
          connect_target: ["done"],
          secret_key: ["done"],
          pause: ["done"],
          backup: ["done"],
          copy_database: ["current", "not_available"],
        },
        {
          pause: { frozen_at: "2026-10-06T12:00:00Z", frozen_by: "alice" },
          backup: {
            location: "s3://acme-backups/langflow",
            confirmed_by: "alice",
            confirmed_at: "2026-10-06T12:30:00Z",
          },
        },
      ),
    );

    expect(
      row("backup").getByText(
        /^Backed up .* to s3:\/\/acme-backups\/langflow\.$/,
      ),
    ).toBeInTheDocument();
    expect(row("backup").queryByRole("button")).not.toBeInTheDocument();
  });

  it("sums up the database copy once it is done, and keeps it one click away", async () => {
    open(
      state(
        { ...copied, copy_database: ["done"] },
        { steps: { copy_database: run("done") } },
      ),
    );

    expect(
      row("copy_database").getByText("Tables: 1,059. Rows: 12,345."),
    ).toBeInTheDocument();
    const again = row("copy_database").getByRole("button", {
      name: "Copy again",
      hidden: true,
    });
    expect(again).not.toBeVisible();
    await userEvent.click(
      row("copy_database").getByRole("button", { name: "Copy the database" }),
    );
    expect(again).toBeVisible();
  });

  it("shows a copy as working while its run is on", () => {
    global.fetch = jest.fn(() => new Promise<Response>(() => {}));
    const marker = () =>
      row("copy_database").getByRole("heading").parentElement
        ?.previousElementSibling;

    const { unmount } = open(state({ ...copied, copy_database: ["current"] }));
    expect(marker()).toHaveClass("bg-primary");
    unmount();

    open(
      state(
        { ...copied, copy_database: ["current"] },
        { steps: { copy_database: run("running") } },
      ),
    );
    expect(marker()).not.toHaveClass("bg-primary");
    expect(row("copy_database").getByText("Starting…")).toBeVisible();
  });

  it("sums up the two store copies once they are done", () => {
    const stores = (counts: Record<string, number>) => ({
      ...run("done"),
      report: { ok: true, counts },
    });
    open(
      state(
        {
          ...copied,
          copy_database: ["done"],
          copy_knowledge_bases: ["done"],
          copy_files: ["done"],
        },
        {
          steps: {
            copy_database: run("done"),
            // One was left behind on the admin's word, so the step is done with one not copied.
            copy_knowledge_bases: stores({
              relocated: 3,
              skipped: 1,
              failed: 1,
            }),
            copy_files: stores({ copied: 1200, skipped: 34, repointed: 9 }),
          },
        },
      ),
    );

    expect(
      row("copy_knowledge_bases").getByText("Copied: 4 of 5"),
    ).toBeInTheDocument();
    expect(
      row("copy_files").getByText("Copied: 1,234 of 1,234"),
    ).toBeInTheDocument();
  });

  it("says a step is not available yet when the server holds it back after the copies", () => {
    open(
      state({
        ...copied,
        copy_database: ["skipped", "already_postgresql"],
        copy_knowledge_bases: ["skipped", "no_local_knowledge_bases"],
        copy_files: ["skipped", "files_in_s3"],
        start_target: ["locked", "not_available"],
        check_target: ["locked", "not_available"],
      }),
    );

    expect(row("start_target").getByText("Coming soon")).toBeInTheDocument();
    expect(row("check_target").getByText("Coming soon")).toBeInTheDocument();
    expect(row("start_target").queryByRole("button")).not.toBeInTheDocument();
    // Nothing above them is left to finish, so a screen reader is not told to finish it.
    expect(
      row("start_target").queryByText("Finish the steps above first."),
    ).not.toBeInTheDocument();
  });

  describe("an acceptance for a list that another copy replaced", () => {
    // The file copy as the record holds it: one file with nothing to copy, which the server offers to accept.
    const left = (id: string, name: string, made = false) =>
      state(
        {
          ...copied,
          copy_database: ["done"],
          copy_knowledge_bases: ["skipped", "no_local_knowledge_bases"],
          copy_files: made ? ["done"] : ["blocked", "no_source_bytes"],
        },
        {
          steps: {
            copy_database: run("done"),
            copy_files: {
              ...run("done"),
              run_id: id,
              report: {
                ok: false,
                counts: { copied: 1, failed: 1 },
                attention: [
                  {
                    subject: `u-1/${name}`,
                    file_name: name,
                    owner: "u-1",
                    code: "no_source_bytes",
                    reason: null,
                    decision: {
                      kind: "accept_missing_attachment",
                      subject: `u-1/${name}`,
                      run_id: id,
                      made: made
                        ? { by: "alice", at: "2026-10-06T12:30:00Z" }
                        : null,
                    },
                  },
                ],
              },
            },
          },
        },
      );
    const line =
      "This copy was made again in the meantime, so your choice was not recorded. The list now shows what the new copy left.";
    const box = (name: string) => ({
      name: `Move without this file, ${name}`,
    });
    /** Opens a page that is one copy behind, accepts the file it shows, and waits for the list the server holds now. */
    const behind = async (now = "new.txt") => {
      const post = jest.spyOn(api, "post").mockRejectedValueOnce(
        Object.assign(new AxiosError("Request failed"), {
          response: {
            status: 409,
            data: { detail: { code: "report_changed" } },
          },
        }),
      );
      // What the server holds by now: another copy, which left another file.
      jest.spyOn(api, "get").mockResolvedValue({ data: left("run-9", now) });
      open(left("run-1", "old.txt"));
      await userEvent.click(
        row("copy_files").getByRole("checkbox", box("old.txt")),
      );
      await row("copy_files").findByText(line);
      const current = row("copy_files").getByRole("checkbox", box(now));
      return { post, current };
    };

    it("says the copy was made again, and shows the list of the copy on record", async () => {
      const { post } = await behind();

      // The acceptance named the list this page had drawn, so the server could tell it was behind.
      expect(post).toHaveBeenCalledWith(expect.stringContaining("decisions"), {
        step: "copy_files",
        kind: "accept_missing_attachment",
        subject: "u-1/old.txt",
        run_id: "run-1",
      });
      expect(row("copy_files").getByText(line)).toBeInTheDocument();
      // One line says it, where the list is.
      expect(
        row("copy_files").queryByText("Something went wrong. Try again."),
      ).not.toBeInTheDocument();
    });

    it("says it once when the new copy left the same file", async () => {
      await behind("old.txt");

      // The box the admin ticked is still there. The line above the list is the answer, with no other under the box.
      expect(row("copy_files").getAllByRole("alert")).toHaveLength(2);
      expect(
        row("copy_files").queryByText("Something went wrong. Try again."),
      ).not.toBeInTheDocument();
    });

    it("drops that line once the admin decides on the list that is there now", async () => {
      const { post, current } = await behind();
      post.mockResolvedValueOnce({ data: left("run-9", "new.txt", true) });

      await userEvent.click(current);

      await waitFor(() =>
        expect(row("copy_files").queryByText(line)).not.toBeInTheDocument(),
      );
      expect(post).toHaveBeenLastCalledWith(
        expect.stringContaining("decisions"),
        {
          step: "copy_files",
          kind: "accept_missing_attachment",
          subject: "u-1/new.txt",
          run_id: "run-9",
        },
      );
    });

    it("drops that line once the admin copies again", async () => {
      const { post } = await behind();
      post.mockResolvedValueOnce({ data: { run_id: "run-10" } });

      await userEvent.click(
        row("copy_files").getByRole("button", { name: "Copy again" }),
      );

      await waitFor(() =>
        expect(row("copy_files").queryByText(line)).not.toBeInTheDocument(),
      );
    });
  });

  it("says how many rows a database copy left out on the admin's word, and counts no row it kept with the key cleared", () => {
    open(
      state(
        { ...copied, copy_database: ["done"] },
        {
          steps: {
            copy_database: {
              ...run("done"),
              report: {
                ok: true,
                tables_copied: 59,
                rows_copied: 57,
                orphans: [
                  {
                    table: "span",
                    column: "trace_id",
                    parent: "trace",
                    ondelete: "CASCADE",
                    rows: 2,
                  },
                  {
                    table: "message",
                    column: "flow_id",
                    parent: "flow",
                    ondelete: "CASCADE",
                    rows: 1200,
                  },
                  // Copied with the key cleared, so already among the rows copied.
                  {
                    table: "authz_role_assignment",
                    column: "assigned_by",
                    parent: "user",
                    ondelete: "SET NULL",
                    rows: 5,
                  },
                ],
              },
            },
          },
        },
      ),
    );

    expect(
      row("copy_database").getByText(
        "Tables: 59. Rows: 57. Rows left out: 1,202",
      ),
    ).toBeInTheDocument();
  });
});
