import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import type { ReactElement } from "react";
import { api } from "@/controllers/API/api";
import type {
  MigrationCopyRun,
  MigrationState,
  MigrationStepState,
} from "@/controllers/API/queries/migration";
import { BackupStep } from "../BackupStep";
import { CopyStep } from "../CopyStep";
import { DestinationsStep } from "../DestinationsStep";
import { PausedBanner, PauseStep, Recovery, Waiting } from "../PauseStep";
import { SecretKeyStep } from "../SecretKeyStep";

// No request leaves these tests. A test that submits first makes the request fail: the connection, as it does when the
// server is gone, or with the refusal the server would send, where the page decides from that answer alone.
const show = (ui: ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>,
  );
const refused = (status: number, detail: object) =>
  Object.assign(new AxiosError("Request failed"), {
    response: { status, data: { detail } },
  });
const unreachable = () =>
  new AxiosError("Network Error", AxiosError.ERR_NETWORK);
const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  jest.restoreAllMocks();
  jest.useRealTimers();
});

const migration = (
  instance: Partial<MigrationState["instance"]> = {},
  record: Partial<MigrationState["record"]> = {},
): MigrationState => ({
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: false },
    ...instance,
  },
  record: { target: {}, steps: {}, accepted_findings: [], ...record },
  steps: [],
  blocking_findings: [],
  acceptable_checks: [],
});

const step = (
  id: MigrationStepState["id"],
  state: MigrationStepState["state"],
  reason?: string,
): MigrationStepState => ({ id, state, reason });

describe("Where your data goes", () => {
  it("asks a SQLite instance with nothing else on its server for a database only", () => {
    show(
      <DestinationsStep
        migration={migration()}
        state={step("connect_target", "current")}
      />,
    );

    // The address holds a password.
    const address = screen.getByLabelText("Connection address");
    expect(address).toHaveAttribute("type", "password");
    expect(address).toBeRequired();
    // How to write it is read out with the field.
    expect(address).toHaveAccessibleDescription(
      /^A new, empty PostgreSQL database/,
    );
    expect(screen.queryByText("Knowledge bases")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Bucket")).not.toBeInTheDocument();
  });

  it("asks a PostgreSQL instance only for what it keeps on its own server", () => {
    show(
      <DestinationsStep
        migration={migration({
          database: {
            type: "postgresql",
            location: "db.internal:5432/langflow",
          },
          knowledge_bases: { local: true },
          files: { storage: "local", local: true },
        })}
        state={step("connect_target", "current")}
      />,
    );

    expect(
      screen.queryByLabelText("Connection address"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/db\.internal:5432\/langflow/)).toBeInTheDocument();
    // Here the knowledge bases go to the store this server reads them from, which is no database of the new instance's.
    expect(
      screen.getByText(
        "This instance already uses PostgreSQL. Its knowledge bases are copied to the store this server reads them from, the one PGVECTOR_CONNECTION_STRING names. That database needs the pgvector extension.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText(/the new instance's database/),
    ).not.toBeInTheDocument();
    for (const label of [
      "Bucket",
      "Folder in the bucket",
      "Access key ID",
      "Secret access key",
    ]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    // Amazon S3 needs no endpoint.
    expect(screen.getByLabelText("Endpoint")).not.toBeRequired();
    expect(screen.getByLabelText("Folder in the bucket")).toHaveValue("files");
    expect(screen.getByLabelText("Access key ID")).not.toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText("Secret access key")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("shows a done step as facts, and asks again without the secrets it never got back", async () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              database: { location: "db.internal:5432/target" },
              files: {
                bucket: "acme",
                prefix: "moved",
                endpoint_url: "https://s3.internal",
              },
              results: { database: { ok: true }, files: { ok: true } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "done")}
      />,
    );

    expect(screen.getByText(/^Saved .* by alice\.$/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Connection address"),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Change or enter again" }),
    );

    expect(screen.getByLabelText("Bucket")).toHaveValue("acme");
    expect(screen.getByLabelText("Folder in the bucket")).toHaveValue("moved");
    expect(screen.getByLabelText("Endpoint")).toHaveValue(
      "https://s3.internal",
    );
    expect(screen.getByLabelText("Connection address")).toHaveValue("");
    expect(screen.getByLabelText("Secret access key")).toHaveValue("");
    // The last test was of what is saved, and says nothing about what the admin types now.
    expect(screen.queryByText("Ready.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByLabelText("Bucket")).not.toBeInTheDocument();
  });

  it("puts what the server found next to each destination, after a reload too", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              database: { location: "db.internal:5432/target" },
              files: { bucket: "acme", prefix: "files" },
              results: {
                database: { ok: true },
                files: {
                  ok: false,
                  code: "bucket_denied",
                  reason: "An error occurred (403) when calling HeadBucket",
                },
              },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "bucket_denied")}
      />,
    );

    expect(screen.getByText("Ready.")).toBeInTheDocument();
    const refusal = screen.getByRole("alert");
    expect(refusal).toHaveTextContent(
      "Access denied. Check the keys and the bucket's permissions.",
    );
    // The server's own words say what it ran into. They are English in every language.
    expect(refusal).toHaveTextContent(
      "An error occurred (403) when calling HeadBucket",
    );
    expect(
      screen.getByText("An error occurred (403) when calling HeadBucket"),
    ).toHaveAttribute("lang", "en");
    // Either key can be the wrong one.
    for (const label of ["Access key ID", "Secret access key"]) {
      const key = screen.getByLabelText(label);
      expect(key).toHaveAttribute("aria-invalid", "true");
      expect(key).toHaveAccessibleDescription(/^Access denied\./);
    }
    expect(screen.getByLabelText("Bucket")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
    expect(screen.getByLabelText("Connection address")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it.each([
    [
      "pgvector_missing",
      "Run CREATE EXTENSION vector; in this database, then test again.",
      "The database needs the pgvector extension. Ask your database admin to turn it on.",
    ],
    [
      "pgvector_package_missing",
      "This server has no pgvector package. Install langflow[pgvector].",
      "This Langflow server doesn't have the pgvector package. Install it, restart Langflow, then test again.",
    ],
  ])(
    "says under Knowledge bases why they can't be copied there: %s",
    (code, reason, line) => {
      show(
        <DestinationsStep
          migration={migration(
            { knowledge_bases: { local: true } },
            {
              destinations: {
                database: { location: "db.internal:5432/target" },
                vectors: { kind: "pgvector" },
                results: {
                  database: { ok: true },
                  vectors: { ok: false, code, reason },
                },
                saved_by: "alice",
                saved_at: "2026-10-06T12:00:00Z",
              },
            },
          )}
          state={step("connect_target", "blocked", code)}
        />,
      );

      // On an instance with its own database file, the knowledge bases go into the new instance's database.
      expect(
        screen.getByText(
          /^Knowledge bases are copied into the new instance's database/,
        ),
      ).toBeInTheDocument();
      const section = screen
        .getByRole("heading", { name: "Knowledge bases" })
        .closest("section") as HTMLElement;
      const refusal = within(section).getByRole("alert");
      expect(refusal).toHaveTextContent(line);
      // The server's own words name what is missing.
      expect(within(refusal).getByText(reason)).toHaveAttribute("lang", "en");
      // The database itself answered, so its field is not the one to look at.
      expect(screen.getByLabelText("Connection address")).toHaveAttribute(
        "aria-invalid",
        "false",
      );
    },
  );

  it("tells an instance on PostgreSQL what its server needs before knowledge bases can be copied", () => {
    show(
      <DestinationsStep
        migration={migration(
          {
            database: {
              type: "postgresql",
              location: "db.internal:5432/langflow",
            },
            knowledge_bases: { local: true },
          },
          {
            destinations: {
              vectors: { kind: "pgvector" },
              results: {
                vectors: {
                  ok: false,
                  code: "pgvector_env_missing",
                  reason: "PGVECTOR_CONNECTION_STRING is not set",
                },
              },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "pgvector_env_missing")}
      />,
    );

    // The note above it says where the knowledge bases go, so the refusal is what to do, and no more.
    const refusal = screen.getByRole("alert");
    expect(refusal.firstElementChild).toHaveTextContent(
      /^Set PGVECTOR_CONNECTION_STRING on this server to that database and restart Langflow, then test again\.$/,
    );
    expect(refusal).toHaveTextContent("PGVECTOR_CONNECTION_STRING is not set");
  });

  it("marks the bucket when it is the bucket that is missing, and gives the server's code when it has no line for it", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              results: {
                database: { ok: false, code: "address_too_new" },
                files: { ok: false, code: "bucket_missing" },
              },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "address_too_new")}
      />,
    );

    const [database, files] = screen.getAllByRole("alert");
    expect(database).toHaveTextContent(/^address_too_new$/);
    expect(files).toHaveTextContent(/^Can't find this bucket\.$/);
    for (const label of ["Connection address", "Bucket"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute(
        "aria-invalid",
        "true",
      );
    }
    expect(screen.getByLabelText("Secret access key")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it("marks the endpoint when the bucket's storage does not answer", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              results: { files: { ok: false, code: "bucket_unreachable" } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "bucket_unreachable")}
      />,
    );

    const endpoint = screen.getByLabelText("Endpoint");
    expect(endpoint).toHaveAttribute("aria-invalid", "true");
    expect(endpoint).toHaveAccessibleDescription(
      /^Can't reach this bucket\. Check the endpoint\./,
    );
    expect(screen.getByLabelText("Bucket")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it("shows a save that never reached the server as failed, and leaves out what the last test found", async () => {
    jest.spyOn(api, "put").mockRejectedValue(unreachable());
    show(
      <DestinationsStep
        migration={migration(
          {},
          {
            destinations: {
              results: { database: { ok: false, code: "db_unreachable" } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "db_unreachable")}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Can't connect to this database.",
    );

    await userEvent.type(
      screen.getByLabelText("Connection address"),
      "postgresql://db.internal/langflow",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Test and save" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^Something went wrong\. Try again\.$/,
    );
  });
});

describe("Hand over the secret key", () => {
  it("says where this instance's key is, and gives the command that prints its fingerprint", () => {
    const { unmount } = show(
      <SecretKeyStep
        migration={migration({
          secret_key: { source: "file", path: "/app/data/secret_key" },
        })}
        state={step("secret_key", "current")}
      />,
    );

    expect(
      screen.getByText(/is in the file \/app\/data\/secret_key on this server/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `printf '%s' "$LANGFLOW_SECRET_KEY" | sha256sum | cut -c1-12`,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/shasum -a 256/)).toBeInTheDocument();
    // Static advice, so it must not interrupt a screen reader as an alert would.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "Do this before 'Start the new instance'.",
    );
    unmount();

    show(
      <SecretKeyStep
        migration={migration({ secret_key: { source: "env" } })}
        state={step("secret_key", "current")}
      />,
    );

    expect(
      screen.getByText(
        /is set in its LANGFLOW_SECRET_KEY environment variable/,
      ),
    ).toBeInTheDocument();
  });

  it("has no room for a pasted key", async () => {
    show(
      <SecretKeyStep
        migration={migration({ secret_key: { source: "env" } })}
        state={step("secret_key", "current")}
      />,
    );
    const field = screen.getByLabelText("What the command printed");
    // Nothing to verify until something is pasted.
    expect(field).toBeRequired();

    await userEvent.click(field);
    await userEvent.paste("k".repeat(44));

    expect(field).toHaveValue("k".repeat(12));
  });

  it("marks the field when the fingerprint is not this instance's", () => {
    show(
      <SecretKeyStep
        migration={migration({ secret_key: { source: "env" } })}
        state={step("secret_key", "blocked", "fingerprint_mismatch")}
      />,
    );

    const field = screen.getByLabelText("What the command printed");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(
      /^This doesn't match this instance's key\./,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This doesn't match this instance's key.",
    );
  });

  it("sends what was pasted, and says so when the server answers that it does not match", async () => {
    const post = jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(400, { code: "fingerprint_mismatch" }));
    show(
      <SecretKeyStep
        migration={migration({ secret_key: { source: "env" } })}
        state={step("secret_key", "current")}
      />,
    );

    await userEvent.type(
      screen.getByLabelText("What the command printed"),
      "000000000000",
    );
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This doesn't match this instance's key.",
    );
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("secret-key/verify"),
      { fingerprint: "000000000000" },
    );
  });

  it("shows a check that never reached the server as failed, and leaves out the last mismatch", async () => {
    jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(
      <SecretKeyStep
        migration={migration({ secret_key: { source: "env" } })}
        state={step("secret_key", "blocked", "fingerprint_mismatch")}
      />,
    );

    await userEvent.type(
      screen.getByLabelText("What the command printed"),
      "0123456789ab",
    );
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));

    expect(
      await screen.findByText("Something went wrong. Try again."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/doesn't match this instance's key/),
    ).not.toBeInTheDocument();
  });
});

const paused = { frozen_at: "2026-10-06T12:00:00Z", frozen_by: "alice" };

describe("Pause changes", () => {
  it("asks before it pauses", async () => {
    show(
      <PauseStep migration={migration()} state={step("pause", "current")} />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Pause changes" }),
    );

    const dialog = screen.getByRole("dialog", { name: "Pause changes now?" });
    expect(dialog).toHaveTextContent("Tell people first.");
    // The dialog wraps its Cancel button in a second one.
    await userEvent.click(
      within(dialog).getAllByRole("button", { name: "Cancel" })[0],
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("lists what is still running, with a way to cancel only what can be cancelled", async () => {
    show(
      <Waiting
        refusal={{
          code: "jobs_active",
          jobs: [
            {
              id: "job-1",
              flow_name: "Support bot",
              owner: "bob",
              state: "suspended",
              started_at: "2026-10-06T11:00:00Z",
              cancel: {
                method: "POST",
                url: "/api/v2/workflows/stop",
                body: { job_id: "job-1" },
              },
            },
            {
              id: "job-2",
              flow_name: "Nightly digest",
              owner: "carol",
              state: "in_progress",
              started_at: "2026-10-06T11:30:00Z",
              cancel: null,
            },
            {
              id: "kb-1",
              flow_name: null,
              knowledge_base: "Handbook",
              owner: "dave",
              state: "ingesting",
              started_at: "2026-10-06T11:45:00Z",
              cancel: {
                method: "POST",
                url: "/api/v1/knowledge_bases/Handbook/cancel",
                body: null,
              },
            },
            {
              id: "job-4",
              flow_name: null,
              owner: null,
              state: "held_elsewhere",
              started_at: "2026-10-06T11:50:00Z",
              cancel: null,
            },
          ],
          listeners: [{ holder: "listener:4242:1a2b3c4d" }],
        }}
      />,
    );

    expect(screen.getByText(/^Still running: 4\./)).toBeInTheDocument();
    // A job with no name goes by its id, and a state this page has no words for by the server's.
    const unnamed = screen.getByTestId("migration-job-job-4");
    expect(unnamed).toHaveTextContent("job-4");
    expect(unnamed).toHaveTextContent("held_elsewhere");
    const waiting = screen.getByTestId("migration-job-job-1");
    expect(waiting).toHaveTextContent("Support bot");
    expect(waiting).toHaveTextContent("bob");
    expect(waiting).toHaveTextContent("Waiting for a person's answer");
    expect(waiting).toHaveTextContent(
      "Cancel it only if the answer is no longer needed.",
    );
    expect(
      screen.getByRole("button", { name: "Cancel run, Support bot" }),
    ).toBeInTheDocument();

    const running = screen.getByTestId("migration-job-job-2");
    expect(running).toHaveTextContent("Running");
    expect(running).toHaveTextContent("You can't cancel this one from here.");
    expect(
      screen.queryByRole("button", { name: /Nightly digest/ }),
    ).not.toBeInTheDocument();

    expect(screen.getByTestId("migration-job-kb-1")).toHaveTextContent(
      "Adding content to a knowledge base",
    );
    expect(
      screen.getByRole("button", { name: "Cancel run, Handbook" }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/^Trigger listeners still running: 1\./),
    ).toBeInTheDocument();
    expect(screen.getByText("listener:4242:1a2b3c4d")).toBeInTheDocument();

    // Cancelling sends the request the server gave for this run. Whatever comes back, the row says how it went.
    const request = jest
      .spyOn(api, "request")
      .mockRejectedValueOnce(unreachable())
      .mockResolvedValueOnce({});
    const cancel = screen.getByRole("button", {
      name: "Cancel run, Support bot",
    });
    await userEvent.click(cancel);
    expect(await within(waiting).findByRole("alert")).toHaveTextContent(
      "Couldn't cancel it.",
    );
    expect(request).toHaveBeenCalledWith({
      method: "POST",
      url: "/api/v2/workflows/stop",
      data: { job_id: "job-1" },
    });
    await userEvent.click(cancel);
    expect(await within(waiting).findByText("Cancel requested.")).toBeVisible();
    expect(cancel).not.toBeInTheDocument();
  });

  it("lists what the server says is still writing, and checks again without asking twice", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(
      refused(409, {
        code: "jobs_active",
        jobs: [
          {
            id: "job-1",
            flow_name: "Support bot",
            owner: "bob",
            state: "in_progress",
            started_at: "2026-10-06T11:00:00Z",
            cancel: null,
          },
        ],
        listeners: [],
      }),
    );
    show(
      <PauseStep migration={migration()} state={step("pause", "current")} />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Pause changes" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Pause",
      }),
    );

    expect(await screen.findByTestId("migration-job-job-1")).toHaveTextContent(
      "Support bot",
    );
    // The list says why, so the line for a request that failed stays away.
    expect(
      screen.queryByText("Something went wrong. Try again."),
    ).not.toBeInTheDocument();

    // The admin agreed to this pause already.
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays blocked until the check has passed again, and says what to do", () => {
    const check = (status: "running" | "done") => ({
      steps: {
        check_source: {
          status,
          started_by: "alice",
          started_at: "2026-10-06T11:00:00Z",
          target_version: "1.13.0",
          exit_code: null,
          report: null,
          error: null,
        },
      },
      pause: paused,
    });
    const { unmount } = show(
      <PauseStep
        migration={migration({}, check("running"))}
        state={step("pause", "blocked", "recheck_pending")}
      />,
    );
    // Read out when it changes, without taking the focus.
    expect(
      screen
        .getByText("Changes are paused. Running the check again…")
        .closest('[aria-live="polite"]'),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    unmount();

    // The page was reloaded, or the run was stopped: the admin starts it again.
    const idle = show(
      <PauseStep
        migration={migration({}, check("done"))}
        state={step("pause", "blocked", "recheck_pending")}
      />,
    );
    expect(
      screen.getByText(
        "Changes are paused. The check has to pass again before you continue.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run again" })).toBeEnabled();
    idle.unmount();

    show(
      <PauseStep
        migration={migration({}, check("done"))}
        state={step("pause", "blocked", "recheck_failed")}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Something changed before the pause. Review 'Check this instance'.",
    );
  });

  it("says that the pause did not begin when it was ended while its request waited", async () => {
    jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(409, { code: "pause_ended" }));
    show(
      <PauseStep migration={migration()} state={step("pause", "current")} />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Pause changes" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Pause",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^The pause did not begin\. Changes were turned back on, or another request/,
    );
  });

  it("says to try again when changes under way had not finished, and does not ask twice", async () => {
    const post = jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(409, { code: "requests_active" }));
    show(
      <PauseStep migration={migration()} state={step("pause", "current")} />,
    );

    const pause = () => screen.getByRole("button", { name: "Pause changes" });
    await userEvent.click(pause());
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Pause",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Changes that were already under way haven't finished yet. Try again in a moment.",
    );
    expect(post).toHaveBeenCalledTimes(1);

    // The admin already agreed to this pause, so trying again is one click.
    await userEvent.click(pause());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  });

  it("shows a pause that never reached the server", async () => {
    jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(
      <PauseStep migration={migration()} state={step("pause", "current")} />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Pause changes" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Pause",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
  });

  it("shows a check that could not start after the pause, and lets the admin run it again", async () => {
    global.fetch = jest
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    show(
      <PauseStep
        migration={migration(
          {},
          { target: { version: "1.13.0" }, pause: paused },
        )}
        state={step("pause", "blocked", "recheck_pending")}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Run again" }));

    expect(
      await screen.findByText("The check couldn't finish."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run again" })).toBeEnabled();
    // It asked for the version the admin checked against before the pause.
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("migration/checks"),
      expect.objectContaining({
        body: JSON.stringify({ target_version: "1.13.0" }),
      }),
    );

    // Another admin's run is already going (409). That is no failure: it shows in the check's own step.
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 409,
      body: null,
    });
    await userEvent.click(screen.getByRole("button", { name: "Run again" }));

    expect(
      await screen.findByRole("button", { name: "Run again" }),
    ).toBeEnabled();
    expect(
      screen.queryByText("The check couldn't finish."),
    ).not.toBeInTheDocument();
  });

  it("keeps a banner up while paused, and confirms before turning changes back on", async () => {
    const { unmount } = show(<PausedBanner migration={migration()} />);
    // There before the pause, so a screen reader hears it start.
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    unmount();

    show(<PausedBanner migration={migration({}, { pause: paused })} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      /^Changes are paused on this instance\. Paused .* by alice\./,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Turn changes back on" }),
    );

    const asked = screen.getByRole("dialog", { name: "Turn changes back on?" });
    expect(asked).toHaveTextContent(
      "The backup and any copies made so far become out of date",
    );

    // Confirmed, it asks the server. The banner says so when that does not get through.
    const resume = jest.spyOn(api, "delete").mockRejectedValue(unreachable());
    await userEvent.click(
      within(asked).getByRole("button", { name: "Resume" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(resume).toHaveBeenCalledTimes(1);
  });

  it("offers the way back from a pause that still waits, or that the server left behind", () => {
    // Changes are refused from the moment a pause is asked for. A server that stops then leaves it so.
    const waiting = migration({}, { pausing: paused });

    const { unmount } = show(<PausedBanner migration={waiting} />);
    // It is not called a pause: the backup and the copies wait for one that has begun.
    expect(screen.getByRole("status")).toHaveTextContent(
      /^Changes are refused\. A pause was asked for and has not begun\. Asked .* by alice\./,
    );
    expect(
      screen.getByRole("button", { name: "Turn changes back on" }),
    ).toBeInTheDocument();
    unmount();

    show(<Recovery migration={waiting} />);
    expect(
      screen.getByText(/^Turn changes back on\. Nothing is lost here\./),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Turn changes back on" }),
    ).toBeInTheDocument();
  });

  it("says how to go back from where the move stands", () => {
    const { unmount } = show(<Recovery migration={migration()} />);
    expect(
      screen.getByText(/^Nothing has changed on this instance\./),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    unmount();

    show(<Recovery migration={migration({}, { pause: paused })} />);
    expect(
      screen.getByText(/^Turn changes back on\. Nothing is lost here\./),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Turn changes back on" }),
    ).toBeInTheDocument();
  });
});

describe("Back up this instance", () => {
  const sqlite = {
    database: { type: "sqlite" as const },
    knowledge_bases: { local: true, folder: "/app/data/knowledge_bases" },
    files: { storage: "local" as const, local: false, folder: "/app/data" },
  };

  it("waits for this pause's copy of a SQLite database", () => {
    const { unmount } = show(
      <BackupStep migration={migration(sqlite, { pause: paused })} />,
    );
    const confirm = () =>
      screen.getByRole("button", { name: "I've backed up everything" });

    expect(
      screen.getByRole("button", { name: "Download the database" }),
    ).toBeEnabled();
    expect(confirm()).toBeDisabled();
    expect(confirm()).toHaveAccessibleDescription(
      "Download the database first.",
    );
    const location = screen.getByLabelText("Where is the backup?");
    expect(location).toBeRequired();
    expect(location).toHaveAccessibleDescription(
      /^Required\. Say where you put the backup/,
    );
    // Nothing is said of a copy until this pause has one.
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    // Only the folders this instance keeps data in.
    expect(
      screen.getByText("Knowledge bases folder: /app/data/knowledge_bases"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Files folder/)).not.toBeInTheDocument();
    // The download is the database alone, and the folders are copied by hand.
    expect(
      screen.getByText(/^This file is the database only\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/^The database copy doesn't hold these folders\./),
    ).toBeInTheDocument();
    unmount();

    // A copy made before changes stopped misses what changed since.
    const stale = show(
      <BackupStep
        migration={migration(sqlite, {
          pause: paused,
          backup: { database_downloaded_at: "2026-10-06T11:59:00Z" },
        })}
      />,
    );
    expect(confirm()).toBeDisabled();
    stale.unmount();

    show(
      <BackupStep
        migration={migration(sqlite, {
          pause: paused,
          backup: { database_downloaded_at: "2026-10-06T12:01:00Z" },
        })}
      />,
    );
    expect(confirm()).toBeEnabled();
    expect(screen.getByRole("status")).toHaveTextContent(/^Downloaded .+\.$/);
  });

  it("shows a download that did not finish, and keeps waiting for one", async () => {
    jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(<BackupStep migration={migration(sqlite, { pause: paused })} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Download the database" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The download didn't finish. Try again.",
    );
    expect(
      screen.getByRole("button", { name: "I've backed up everything" }),
    ).toBeDisabled();
  });

  it("says to download first when the server finds no copy from this pause", async () => {
    jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(409, { code: "database_not_downloaded" }));
    // The page still holds a copy the server no longer counts, as after a pause that started again elsewhere.
    show(
      <BackupStep
        migration={migration(sqlite, {
          pause: paused,
          backup: {
            database_downloaded_at: "2026-10-06T12:01:00Z",
            location: "s3://backups/langflow",
          },
        })}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "I've backed up everything" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^Download the database first\.$/,
    );
  });

  it("gives a PostgreSQL instance a command with its host and database, and no user", () => {
    show(
      <BackupStep
        migration={migration(
          {
            database: {
              type: "postgresql",
              location: "db.internal:5432/langflow",
            },
            // The folder is there, with nothing of this instance's in it.
            knowledge_bases: {
              local: false,
              folder: "/app/data/knowledge_bases",
            },
            files: { storage: "local", local: true, folder: "/app/data" },
          },
          { pause: paused },
        )}
      />,
    );

    expect(
      screen.getByText(
        "pg_dump -h db.internal -p 5432 -d langflow -F c -f langflow-backup.dump",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/^Knowledge bases folder/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download the database" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Files folder: /app/data")).toBeInTheDocument();
    // No download on this page, so the line under the folders speaks of the database copy.
    expect(
      screen.getByText(/^The database copy doesn't hold these folders\./),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/^This file is the database only\./),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "I've backed up everything" }),
    ).toBeEnabled();
  });

  it("starts from the place the record already names, and shows a confirmation that never reached the server", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(
      <BackupStep
        migration={migration(
          {
            database: {
              type: "postgresql",
              location: "db.internal:5432/langflow",
            },
          },
          { pause: paused, backup: { location: "s3://backups/langflow" } },
        )}
      />,
    );
    expect(screen.getByLabelText("Where is the backup?")).toHaveValue(
      "s3://backups/langflow",
    );
    // Nothing on this server to copy by hand, so no advice about folders.
    expect(
      screen.queryByText(/^The database copy doesn't hold these folders\./),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "I've backed up everything" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("steps/backup/confirm"),
      { location: "s3://backups/langflow" },
    );
  });
});

describe("Copy the database", () => {
  const copying = (run?: Partial<MigrationCopyRun>) =>
    migration(
      {},
      {
        steps: {
          copy_database: run && {
            run_id: "run-1",
            status: "done",
            dry_run: false,
            started_by: "alice",
            started_at: "2026-10-06T12:05:00Z",
            finished_at: "2026-10-06T12:06:00Z",
            report: null,
            error: null,
            ...run,
          },
        },
      },
    );
  const panel = (
    run: Partial<MigrationCopyRun> | undefined,
    ...where: [MigrationStepState["state"], string?]
  ) => (
    <CopyStep
      migration={copying(run)}
      state={step("copy_database", ...where)}
      step="copy_database"
    />
  );
  // A stream as the server sends one: each line an event. It ends, or the connection drops.
  const stream = (lines: object[], dropped = false) => {
    const chunks = [
      Buffer.from(lines.map((line) => `${JSON.stringify(line)}\n\n`).join("")),
    ];
    return {
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: async () => {
            const value = chunks.shift();
            if (!value && dropped) throw new TypeError("network error");
            return { done: !value, value };
          },
        }),
      },
    };
  };
  // A refusal as the server sends one: a status and one JSON error body.
  const refusedStream = (status: number, detail: object) => ({
    ...stream([{ detail }]),
    ok: false,
    status,
  });
  // A stream that stays open and says nothing.
  const silent = () => jest.fn(() => new Promise<Response>(() => {}));

  it("offers the copy and sends it as a real run", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(panel(undefined, "current"));

    expect(
      screen.getByText(/^Copies every table in one go\./),
    ).toBeInTheDocument();
    // The database copy has no way to try it first.
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByText(/out of date/)).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Copy the database" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("steps/copy_database/runs"),
      { dry_run: false },
    );
  });

  it.each([
    [
      "secrets_missing",
      "Langflow no longer holds the passwords and keys of the new instance. Enter them again in 'Where your data goes'.",
    ],
    ["run_active", "Another step is running. Wait for it to finish."],
    // A step above opened again in another tab, and this page has not read that yet.
    ["locked", "Finish the steps above first."],
  ])("says why the server would not start it: %s", async (code, line) => {
    jest.spyOn(api, "post").mockRejectedValue(refused(409, { code }));
    show(panel(undefined, "current"));

    await userEvent.click(
      screen.getByRole("button", { name: "Copy the database" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(line);
  });

  it("follows a run from the last line it saw, and reads the record again when it ends", async () => {
    jest.useFakeTimers();
    const fetched = jest
      .fn()
      .mockResolvedValueOnce(
        stream(
          [
            {
              event: "progress",
              phase: "checking",
              done: 0,
              total: null,
              seq: 1,
            },
            {
              event: "progress",
              phase: "copying",
              done: 10,
              total: 57,
              seq: 2,
            },
          ],
          true,
        ),
      )
      .mockResolvedValueOnce(
        stream([{ event: "end", status: "done", exit_code: 0, seq: 3 }]),
      );
    global.fetch = fetched;
    const client = new QueryClient();
    const reread = jest.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        {panel({ status: "running", finished_at: null }, "current")}
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Rows: 10 of 57")).toBeInTheDocument();
    expect(fetched.mock.calls[0][0]).toContain(
      "steps/copy_database/runs/run-1/events?after=0",
    );
    expect(reread).not.toHaveBeenCalled();

    // The connection dropped. After a moment the page asks again for what came after the last line it saw.
    await act(() => jest.advanceTimersByTimeAsync(1000));
    expect(fetched).toHaveBeenCalledTimes(1);
    await act(() => jest.advanceTimersByTimeAsync(1000));

    expect(fetched.mock.calls[1][0]).toContain("events?after=2");
    await waitFor(() => expect(reread).toHaveBeenCalledTimes(1));
  });

  it("stops asking for a run the server no longer has, and reads the record again", async () => {
    jest.useFakeTimers();
    const fetched = jest
      .fn()
      .mockImplementation(async () =>
        refusedStream(404, { code: "run_not_found" }),
      );
    global.fetch = fetched;
    const client = new QueryClient();
    const reread = jest.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        {panel({ status: "running", finished_at: null }, "current")}
      </QueryClientProvider>,
    );

    await waitFor(() => expect(reread).toHaveBeenCalledTimes(1));
    await act(() => jest.advanceTimersByTimeAsync(10000));
    expect(fetched).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Starting…")).toBeInTheDocument();
  });

  it("asks again after any other refusal, and reads nothing from its body", async () => {
    jest.useFakeTimers();
    const fetched = jest
      .fn()
      .mockImplementationOnce(async () =>
        refusedStream(500, { message: "boom" }),
      )
      .mockImplementation(() => new Promise<Response>(() => {}));
    global.fetch = fetched;
    const client = new QueryClient();
    const reread = jest.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        {panel({ status: "running", finished_at: null }, "current")}
      </QueryClientProvider>,
    );

    await waitFor(() => expect(fetched).toHaveBeenCalledTimes(1));
    await act(() => jest.advanceTimersByTimeAsync(2000));

    expect(fetched).toHaveBeenCalledTimes(2);
    expect(fetched.mock.calls[1][0]).toContain("events?after=0");
    expect(reread).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Starting…");
  });

  it("says when a copy it was following has ended", () => {
    global.fetch = silent();
    const client = new QueryClient();
    const { rerender } = render(
      <QueryClientProvider client={client}>
        {panel({ status: "running", finished_at: null }, "current")}
      </QueryClientProvider>,
    );
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("Starting…");

    rerender(
      <QueryClientProvider client={client}>
        {panel(
          { report: { ok: true, tables_copied: 59, rows_copied: 1234 } },
          "done",
        )}
      </QueryClientProvider>,
    );

    // The same region stays mounted, so a screen reader hears the result.
    expect(screen.getByRole("status")).toBe(region);
    expect(region).toHaveTextContent("Tables: 59. Rows: 1,234.");
  });

  it("asks before it stops a run, and lets go of the run when the page goes away", async () => {
    const fetched = silent();
    global.fetch = fetched;
    const stop = jest.spyOn(api, "delete").mockRejectedValue(unreachable());
    const { unmount } = show(
      panel({ status: "running", finished_at: null }, "current"),
    );

    expect(screen.getByText("Starting…")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Copy/ }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));

    const asked = screen.getByRole("dialog", { name: "Stop copying?" });
    expect(asked).toHaveTextContent("Nothing from a stopped copy is kept.");
    await userEvent.click(
      within(asked).getAllByRole("button", { name: "Cancel" })[0],
    );
    expect(stop).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Stop" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(stop).toHaveBeenCalledWith(
      expect.stringContaining("steps/copy_database/runs/run-1"),
    );

    // Leaving the page stops listening and nothing else: the run is the server's.
    const [, { signal }] = fetched.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
  });

  it.each<[string, Partial<MigrationCopyRun>, string, string | undefined]>([
    [
      "target_unreachable",
      {
        report: {
          ok: false,
          problems: [
            { code: "target_unreachable", message: "connection refused" },
          ],
        },
      },
      "Can't reach the new instance's database. Check 'Where your data goes', then try again.",
      "connection refused",
    ],
    [
      "target_not_empty",
      {
        report: {
          ok: false,
          problems: [
            { code: "target_not_empty", message: "at revision abc" },
            { code: "value_rejected", message: "bad enum" },
          ],
        },
      },
      "The new instance's database isn't empty. Use a new, empty database, change it in 'Where your data goes', then copy again.",
      "at revision abc bad enum",
    ],
    // The destination holds an earlier copy, and a row was deleted here since. Copying again cannot get past it.
    [
      "count_mismatch",
      {
        report: {
          ok: false,
          problems: [
            {
              code: "count_mismatch",
              message: "file: source has 1 rows, target has 2 after copy",
            },
          ],
        },
      },
      "The new instance's database holds an earlier copy that no longer matches this instance. Copying into it again can't fix that. Save a new, empty database in 'Where your data goes', then copy again.",
      "file: source has 1 rows, target has 2 after copy",
    ],
    [
      "crashed",
      {
        status: "failed",
        error: { code: "crashed", message: "Traceback: boom" },
      },
      "The step stopped with an error. Run it again.",
      "Traceback: boom",
    ],
    // A code this page has no words for reads as a failure, with the tool's own words under it.
    [
      "copy_failed",
      {
        report: {
          ok: false,
          problems: [{ code: "copy_failed", message: "rolled back" }],
        },
      },
      "The step stopped with an error. Run it again.",
      "rolled back",
    ],
    [
      "cancelled",
      { status: "cancelled", error: { code: "cancelled" } },
      "Stopped before it finished. Run it again.",
      undefined,
    ],
    [
      "destination_changed",
      { report: { ok: true, tables_copied: 59, rows_copied: 57 } },
      "The destination changed after this copy was made. Copy again.",
      undefined,
    ],
  ])("says why the last copy does not count: %s", (reason, run, line, said) => {
    show(panel(run, "blocked", reason));

    const why = screen.getByRole("alert");
    expect(why).toHaveTextContent(line);
    if (said)
      expect(within(why).getByText(/./, { selector: "pre" })).toHaveTextContent(
        said,
      );
    else expect(why.querySelector("pre")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
  });

  it("offers a done copy again, with nothing to explain", () => {
    show(
      panel(
        { report: { ok: true, tables_copied: 59, rows_copied: 57 } },
        "done",
      ),
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/out of date/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
  });

  it("says a copy the step no longer counts has to be made again", () => {
    // The copy ended well, and the step waits again: the instance changed after it.
    show(
      panel(
        { report: { ok: true, tables_copied: 59, rows_copied: 57 } },
        "current",
      ),
    );

    expect(
      screen.getByText(
        "This copy is out of date, so it no longer counts. Copy again.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
  });
});

describe("Copy knowledge bases and files", () => {
  const ended = (
    step: "copy_knowledge_bases" | "copy_files",
    run?: Partial<MigrationCopyRun>,
    instance: Parameters<typeof migration>[0] = {},
  ) =>
    migration(instance, {
      steps: {
        [step]: run && {
          run_id: "run-2",
          status: "done",
          dry_run: false,
          started_by: "alice",
          started_at: "2026-10-06T12:10:00Z",
          finished_at: "2026-10-06T12:11:00Z",
          report: null,
          error: null,
          ...run,
        },
      },
    });
  const kb = (code: string, name: string, reason: string | null = null) => ({
    subject: `id-${name}`,
    kb_name: name,
    owner: "bob",
    code,
    reason,
  });
  const file = (code: string, name: string, reason: string | null = null) => ({
    subject: `u-1/${name}`,
    file_name: name,
    owner: "u-1",
    code,
    reason,
  });

  it("offers a test run before the copy, and sends each as what it is", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    show(
      <CopyStep
        migration={ended("copy_knowledge_bases")}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );
    expect(
      screen.getByText(/^A test run says what would be copied/),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Test run" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Copy knowledge bases" }),
    );

    const runs = expect.stringContaining("steps/copy_knowledge_bases/runs");
    expect(post).toHaveBeenNthCalledWith(1, runs, { dry_run: true });
    expect(post).toHaveBeenNthCalledWith(2, runs, { dry_run: false });
  });

  // Every step above the knowledge base copy, as the server lists them.
  const above = (
    check: MigrationStepState,
    database = step("copy_database", "done"),
  ) => [
    check,
    step("connect_target", "done"),
    step("secret_key", "done"),
    step(
      "pause",
      check.state === "done" ? "done" : "blocked",
      "recheck_failed",
    ),
    step("backup", "done"),
    database,
  ];

  it("offers no start, real or test, while a step before it is open again, and says why", () => {
    // The check failed again after this copy. The copy keeps its place, and the server would refuse to start it.
    show(
      <CopyStep
        migration={{
          ...ended("copy_knowledge_bases", {
            report: { ok: true, counts: { relocated: 3 }, attention: [] },
          }),
          steps: [
            ...above(step("check_source", "blocked", "blocking_findings")),
            step("copy_knowledge_bases", "done"),
            step("copy_files", "done"),
          ],
        }}
        state={step("copy_knowledge_bases", "done")}
        step="copy_knowledge_bases"
      />,
    );

    // What the copy did is still there to read.
    expect(
      screen.getByText("Copied: 3. Already copied: 0. Not copied: 0."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText("Finish the steps above first."),
    ).toBeInTheDocument();
  });

  it("moves the focus to its line when the state closes the gate under a focused start", () => {
    // A copy that ran, and every step before it done: the start is offered.
    const at = (check: MigrationStepState) => (
      <CopyStep
        migration={{
          ...ended("copy_knowledge_bases", {
            report: { ok: true, counts: { relocated: 3 }, attention: [] },
          }),
          steps: [
            ...above(check),
            step("copy_knowledge_bases", "done"),
            step("copy_files", "done"),
          ],
        }}
        state={step("copy_knowledge_bases", "done")}
        step="copy_knowledge_bases"
      />
    );
    const client = new QueryClient();
    const { rerender } = render(
      <QueryClientProvider client={client}>
        {at(step("check_source", "done"))}
      </QueryClientProvider>,
    );
    act(() => screen.getByRole("button", { name: "Copy again" }).focus());

    // A read of the state, after a refused start or on the poll, finds the check open again.
    rerender(
      <QueryClientProvider client={client}>
        {at(step("check_source", "blocked", "blocking_findings"))}
      </QueryClientProvider>,
    );

    // The button is gone, and the keyboard lands on the line that says why, which is announced.
    // What the copy found is a status too, so the line is found by its words.
    const line = screen.getByText("Finish the steps above first.");
    expect(line).toHaveAttribute("role", "status");
    expect(line).toHaveFocus();
  });

  it("leaves the focus alone when the gate closes while it is elsewhere", () => {
    const at = (check: MigrationStepState) => (
      <CopyStep
        migration={{
          ...ended("copy_knowledge_bases"),
          steps: [
            ...above(check),
            step("copy_knowledge_bases", "current"),
            step("copy_files", "locked", "earlier_step"),
          ],
        }}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />
    );
    const client = new QueryClient();
    const { rerender } = render(
      <QueryClientProvider client={client}>
        {at(step("check_source", "done"))}
      </QueryClientProvider>,
    );
    rerender(
      <QueryClientProvider client={client}>
        {at(step("check_source", "blocked", "blocking_findings"))}
      </QueryClientProvider>,
    );

    expect(screen.getByText("Finish the steps above first.")).not.toHaveFocus();
  });

  it("offers the start when every step before it is done or not needed, whatever comes after it", () => {
    show(
      <CopyStep
        migration={{
          ...ended("copy_knowledge_bases"),
          steps: [
            ...above(
              step("check_source", "done"),
              step("copy_database", "skipped", "already_postgresql"),
            ),
            step("copy_knowledge_bases", "current"),
            step("copy_files", "locked", "earlier_step"),
          ],
        }}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Copy knowledge bases" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Test run" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Finish the steps above first."),
    ).not.toBeInTheDocument();
  });

  it("says what a test run found, and still offers the first copy", () => {
    show(
      <CopyStep
        migration={ended("copy_knowledge_bases", {
          dry_run: true,
          report: {
            ok: false,
            counts: { would_relocate: 2, skipped: 1, failed: 1 },
            attention: [kb("kb_ingesting", "handbook")],
          },
        })}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );

    expect(
      screen.getByText(
        "Test run: nothing was copied. To copy: 2. Already copied: 1. Can't be copied: 1.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "handbook (bob)It is still adding content.",
    );
    // A test run completes nothing and blocks nothing, and it is no copy that could be out of date.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/out of date/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copy knowledge bases" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Copy again" }),
    ).not.toBeInTheDocument();
  });

  it("sends one start at a time", async () => {
    // The first start is still on its way.
    const post = jest
      .spyOn(api, "post")
      .mockImplementation(() => new Promise(() => {}));
    show(
      <CopyStep
        migration={ended("copy_files")}
        state={step("copy_files", "current")}
        step="copy_files"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Copy files" }));
    const test = screen.getByRole("button", { name: "Test run" });
    expect(test).toBeDisabled();
    await userEvent.click(test);

    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("steps/copy_files/runs"),
      { dry_run: false },
    );
  });

  it("reads out what a test run found, in the node that read its progress", () => {
    // The run's progress never comes.
    global.fetch = jest.fn(() => new Promise<Response>(() => {}));
    const running = { status: "running" as const, dry_run: true };
    const { rerender } = show(
      <CopyStep
        migration={ended("copy_knowledge_bases", running)}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );
    const said = screen.getByRole("status");
    expect(said).toHaveTextContent("Starting…");

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CopyStep
          migration={ended("copy_knowledge_bases", {
            dry_run: true,
            report: { ok: true, counts: { would_relocate: 3 } },
          })}
          state={step("copy_knowledge_bases", "current")}
          step="copy_knowledge_bases"
        />
      </QueryClientProvider>,
    );

    // A screen reader reads a change to a live region it already knows, not a new one.
    expect(screen.getByRole("status")).toBe(said);
    expect(said).toHaveAttribute("aria-live", "polite");
    expect(said).toHaveTextContent(
      /^Test run: nothing was copied\. To copy: 3\./,
    );
  });

  it("offers no test run once the copy is done, since one would take the copy's place", () => {
    show(
      <CopyStep
        migration={ended("copy_knowledge_bases", {
          report: { ok: true, counts: { relocated: 1 } },
        })}
        state={step("copy_knowledge_bases", "done")}
        step="copy_knowledge_bases"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Test run" }),
    ).not.toBeInTheDocument();
  });

  it("lists each knowledge base a copy left, with the page's line and the tool's words", () => {
    show(
      <CopyStep
        migration={ended("copy_knowledge_bases", {
          report: {
            ok: false,
            counts: { relocated: 3, failed: 250 },
            attention: [
              kb("kb_backend_missing", "legacy", "backend 'astra' is gone"),
              kb("kb_upgrade_pending", "old"),
              kb("kb_metric_unknown", "odd", "no metric in the mapping"),
            ],
          },
        })}
        state={step("copy_knowledge_bases", "blocked", "kb_backend_missing")}
        step="copy_knowledge_bases"
      />,
    );

    expect(
      screen.getByText("Copied: 3. Already copied: 0. Not copied: 250."),
    ).toBeInTheDocument();
    // What stops the step is in the list, so the step's own line only points at it.
    expect(screen.getByRole("alert")).toHaveTextContent(
      /^Some were not copied\. Each one below says why\.$/,
    );
    const [legacy, old, odd] = screen.getAllByRole("listitem");
    expect(legacy).toHaveTextContent(
      "legacy (bob)It uses a store this version can't open.",
    );
    expect(within(legacy).getByText("backend 'astra' is gone")).toHaveAttribute(
      "lang",
      "en",
    );
    // The command gives this code to an upgrade that has not finished and to a store it can never read.
    expect(old).toHaveTextContent(
      "This version can't read its storage as it is now. Details says why.",
    );
    expect(old.querySelector("pre")).toBeNull();
    // A code this page has no line for.
    expect(odd).toHaveTextContent("It wasn't copied.");
    expect(odd).toHaveTextContent("no metric in the mapping");
    // The record keeps the first of them only.
    expect(screen.getByText("Showing the first 3 of 250.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
  });

  it("words each file that was not copied", () => {
    show(
      <CopyStep
        migration={ended("copy_files", {
          report: {
            ok: false,
            counts: { copied: 1200, skipped: 34, failed: 4 },
            attention: [
              file("file_conflict", "cat.txt"),
              file("bad_name", "a\\b.txt"),
              file("no_source_bytes", "gone.txt"),
              file("bucket_error", "big.bin", "SlowDown"),
            ],
          },
        })}
        state={step("copy_files", "blocked", "file_conflict")}
        step="copy_files"
      />,
    );

    expect(
      screen.getByText("Copied: 1,200. Already copied: 34. Not copied: 4."),
    ).toBeInTheDocument();
    const lines = screen
      .getAllByRole("listitem")
      .map((item) => item.textContent);
    expect(lines).toEqual([
      "cat.txt (u-1)The bucket already holds a different file with this name. Nothing is overwritten.",
      "a\\b.txt (u-1)This file's stored name has a backslash or \"..\" in it, which Langflow's file storage refuses, so it can't be copied.",
      "gone.txt (u-1)Nothing is stored for this name, so there is nothing to copy. It will show as missing.",
      "big.bin (u-1)Can't write to the bucket. Check 'Where your data goes', then try again.Details, big.binSlowDown",
    ]);
    expect(screen.queryByText(/^Showing the first/)).not.toBeInTheDocument();
    // The file copy can be tried first as well.
    expect(
      screen.getByRole("button", { name: "Test run" }),
    ).toBeInTheDocument();
  });

  it("lists two chat messages that miss the same file apart", () => {
    // The command reports one for each message, under the same owner and name.
    const logged = jest.spyOn(console, "error").mockImplementation(() => {});
    show(
      <CopyStep
        migration={ended("copy_files", {
          report: {
            ok: false,
            counts: { copied: 3, failed: 2 },
            attention: [
              file("attachment_unmatched", "cat.png", "in message 1"),
              file("attachment_unmatched", "cat.png", "in message 2"),
            ],
          },
        })}
        state={step("copy_files", "blocked", "attachment_unmatched")}
        step="copy_files"
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("in message 1");
    expect(rows[1]).toHaveTextContent("in message 2");
    // React says so when two rows of a list go by the same key.
    expect(logged).not.toHaveBeenCalled();
  });

  it("shows nothing of a copy the step no longer counts, and says to copy again", () => {
    show(
      <CopyStep
        migration={ended("copy_files", {
          report: {
            ok: false,
            counts: { copied: 9, failed: 1 },
            attention: [file("file_conflict", "cat.txt", "sizes differ")],
          },
        })}
        state={step("copy_files", "current")}
        step="copy_files"
      />,
    );

    expect(
      screen.getByText(
        "This copy is out of date, so it no longer counts. Copy again.",
      ),
    ).toBeInTheDocument();
    // What it found is no result any more.
    expect(screen.queryByText(/^Copied:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copy again" }),
    ).toBeInTheDocument();
  });

  it("says why a run ended without a report, whether it was a test or the copy", () => {
    const stopped = {
      status: "failed" as const,
      error: { code: "bucket_error", message: "AccessDenied on HeadBucket" },
    };
    const { unmount } = show(
      <CopyStep
        migration={ended("copy_files", { ...stopped, dry_run: true })}
        state={step("copy_files", "current")}
        step="copy_files"
      />,
    );
    const why = () => screen.getByRole("alert");
    expect(why()).toHaveTextContent(
      "Can't write to the bucket. Check 'Where your data goes', then try again.",
    );
    expect(why()).toHaveTextContent("AccessDenied on HeadBucket");
    unmount();

    const { unmount: unmount2 } = show(
      <CopyStep
        migration={ended("copy_files", stopped)}
        state={step("copy_files", "blocked", "bucket_error")}
        step="copy_files"
      />,
    );
    expect(why()).toHaveTextContent("Can't write to the bucket.");
    unmount2();

    // A copy from an earlier pause no longer counts, and what went wrong with it is no longer news.
    show(
      <CopyStep
        migration={ended("copy_files", stopped)}
        state={step("copy_files", "current")}
        step="copy_files"
      />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says what an instance on PostgreSQL has to set before its knowledge bases are copied", async () => {
    jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(409, { code: "pgvector_env_missing" }));
    show(
      <CopyStep
        migration={ended("copy_knowledge_bases", undefined, {
          database: { type: "postgresql", location: "db:5432/langflow" },
        })}
        state={step("copy_knowledge_bases", "blocked", "pgvector_env_missing")}
        step="copy_knowledge_bases"
      />,
    );
    // The note above says the store changes but not which one, so this line names it before it asks for the variable.
    expect(
      screen.getByText(/^This instance uses PostgreSQL, so it switches/),
    ).toBeInTheDocument();
    const line =
      "This instance already uses PostgreSQL, so its knowledge bases are copied to the store this server reads them from. Set PGVECTOR_CONNECTION_STRING on this server to that database and restart Langflow, then copy again.";

    // Nothing ran, and the step says why it will not.
    expect(screen.getByRole("alert")).toHaveTextContent(line);

    await userEvent.click(
      screen.getByRole("button", { name: "Copy knowledge bases" }),
    );

    // A start is refused for the same reason, in the same words.
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    for (const alert of screen.getAllByRole("alert"))
      expect(alert).toHaveTextContent(line);
  });

  it("warns an instance on PostgreSQL that its own knowledge bases move too", () => {
    const postgresql = {
      database: { type: "postgresql" as const, location: "db:5432/langflow" },
    };
    const note = () => screen.queryByText(/^This instance uses PostgreSQL/);
    const { unmount } = show(
      <CopyStep
        migration={ended("copy_knowledge_bases", undefined, postgresql)}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );
    expect(note()).toBeInTheDocument();
    unmount();

    const files = show(
      <CopyStep
        migration={ended("copy_files", undefined, postgresql)}
        state={step("copy_files", "current")}
        step="copy_files"
      />,
    );
    expect(note()).not.toBeInTheDocument();
    files.unmount();

    show(
      <CopyStep
        migration={ended("copy_knowledge_bases")}
        state={step("copy_knowledge_bases", "current")}
        step="copy_knowledge_bases"
      />,
    );
    expect(note()).not.toBeInTheDocument();
  });
});

describe("What the admin decides about a copy", () => {
  const panel = (
    id: "copy_database" | "copy_knowledge_bases" | "copy_files",
    run: Partial<MigrationCopyRun>,
    state: MigrationStepState["state"] = "blocked",
  ) => (
    <CopyStep
      migration={migration(
        {},
        {
          steps: {
            [id]: {
              run_id: "run-3",
              status: "done",
              dry_run: false,
              started_by: "alice",
              started_at: "2026-10-06T12:20:00Z",
              finished_at: "2026-10-06T12:21:00Z",
              report: null,
              error: null,
              ...run,
            },
          },
        },
      )}
      state={step(id, state, state === "blocked" ? "decide" : undefined)}
      step={id}
    />
  );
  // A failed item as the record holds it. The server says which decision answers its code, if one does,
  // and who made it when it is in effect. One that names the item accepts it, and one that names none
  // is an option for the whole step.
  const alice = { by: "alice", at: "2026-10-06T12:30:00Z" };
  const item = (
    code: string,
    name: string,
    kind?: string,
    { files = false, option = false, made = false } = {},
  ) => {
    const subject = files ? `u-1/${name}` : `id-${name}`;
    return {
      subject,
      [files ? "file_name" : "kb_name"]: name,
      owner: files ? "u-1" : "bob",
      code,
      reason: null,
      decision: kind
        ? {
            kind,
            subject: option ? null : subject,
            run_id: option ? null : "run-3",
            made: made ? alice : null,
          }
        : null,
    };
  };
  const boxes = () =>
    screen
      .getAllByRole("checkbox")
      .map((box) => box.getAttribute("aria-label"));
  const orphans = (
    decision: {
      kind: string;
      subject: null;
      run_id: null;
      made: typeof alice | null;
    } | null,
  ) => ({
    report: {
      ok: false,
      problems: [{ code: "orphans_droppable", message: "re-run the copy" }],
    },
    decision_needed: {
      code: "orphans_droppable",
      details: {
        orphans: [
          {
            table: "span",
            column: "trace_id",
            parent: "trace",
            ondelete: "CASCADE",
            rows: 2,
          },
        ],
      },
      decision,
    },
  });
  const dropOrphans = (made = false) => ({
    kind: "drop_orphans",
    subject: null,
    run_id: null,
    made: made ? alice : null,
  });
  const note = () => screen.queryByText(/^Accepting a finding/);

  it("says a row whose key is cleared is copied, not left out", () => {
    const asked = orphans(dropOrphans());
    asked.decision_needed.details.orphans.push({
      table: "authz_role_assignment",
      column: "assigned_by",
      parent: "user",
      ondelete: "SET NULL",
      rows: 3,
    });
    show(panel("copy_database", asked));

    expect(
      screen.getAllByRole("listitem").map((item) => item.textContent),
    ).toEqual([
      "Rows in span that point at deleted rows of trace: 2",
      "Rows in authz_role_assignment that point at deleted rows of user: 3. They are copied with assigned_by cleared.",
    ]);
  });

  it("shows the rows a database copy would leave out, and asks before it does", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    render(
      <QueryClientProvider client={new QueryClient()}>
        <CopyStep
          migration={migration(
            {},
            {
              steps: {
                copy_database: {
                  run_id: "run-3",
                  status: "done",
                  dry_run: false,
                  started_by: "alice",
                  started_at: "2026-10-06T12:20:00Z",
                  finished_at: "2026-10-06T12:21:00Z",
                  error: null,
                  ...orphans(dropOrphans()),
                },
              },
            },
          )}
          state={step("copy_database", "blocked", "orphans_droppable")}
          step="copy_database"
        />
      </QueryClientProvider>,
    );

    expect(screen.getAllByRole("alert")[0]).toHaveTextContent(
      "Some rows belong to deleted items",
    );
    expect(
      screen.getByText(/^They point at items deleted earlier/),
    ).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "Rows in span that point at deleted rows of trace: 2",
    );
    const leaveOut = screen.getByRole("checkbox", {
      name: "Leave out or unlink these rows and copy the rest",
    });
    expect(leaveOut).not.toBeChecked();
    // Nothing says it was decided until it is.
    expect(screen.queryByText(/^Accepted by /)).not.toBeInTheDocument();
    expect(
      screen.queryByText("This applies to the next copy."),
    ).not.toBeInTheDocument();

    await userEvent.click(leaveOut);

    // The decision goes back as the server named it, and no more. An option belongs to no one run.
    expect(post).toHaveBeenCalledWith(expect.stringContaining("decisions"), {
      step: "copy_database",
      kind: "drop_orphans",
      subject: null,
      run_id: null,
    });
    expect(
      await screen.findByText("Something went wrong. Try again."),
    ).toBeInTheDocument();
  });

  it("asks nothing the server does not offer, and nothing about a copy that no longer counts", () => {
    const { unmount } = show(panel("copy_database", orphans(null)));
    // The rows are what the copy found. Whether they can be left out is the server's to say.
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "Rows in span that point at deleted rows of trace: 2",
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    unmount();

    show(panel("copy_database", orphans(dropOrphans()), "current"));
    expect(screen.getByText(/out of date/)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("ticks a decision the server says is in effect, says who made it, and takes it back", async () => {
    const withdrawn = jest
      .spyOn(api, "delete")
      .mockRejectedValue(unreachable());
    show(panel("copy_database", orphans(dropOrphans(true))));

    const leaveOut = screen.getByRole("checkbox", {
      name: "Leave out or unlink these rows and copy the rest",
    });
    expect(leaveOut).toBeChecked();
    // Who decided and when come with the decision, and the time reads as times do on this page.
    expect(
      screen.getByText(/^Accepted by alice on .*2026/),
    ).not.toHaveTextContent("2026-10-06T12:30:00Z");
    // An option changes the next copy, and nothing about the one that asked.
    expect(
      screen.getByText("This applies to the next copy."),
    ).toBeInTheDocument();

    await userEvent.click(leaveOut);

    expect(withdrawn).toHaveBeenCalledWith(
      expect.stringContaining("decisions"),
      {
        data: {
          step: "copy_database",
          kind: "drop_orphans",
          subject: null,
          run_id: null,
        },
      },
    );
  });

  it("asks once about an option several knowledge bases wait for, and offers each what the server offers it", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    const withdrawn = jest
      .spyOn(api, "delete")
      .mockRejectedValue(unreachable());
    const ranking = { option: true };
    show(
      panel("copy_knowledge_bases", {
        report: {
          ok: false,
          counts: { relocated: 1, failed: 6 },
          attention: [
            item("kb_metric_change", "notes", "accept_ranking_change", ranking),
            item("kb_metric_change", "wiki", "accept_ranking_change", ranking),
            // The server says this one's acceptance is in effect, and the next one's is not.
            item("kb_backend_missing", "legacy", "leave_behind", {
              made: true,
            }),
            item("kb_backend_missing", "lost", "leave_behind"),
            // One that can be put right and copied again has no decision.
            item("kb_upgrade_pending", "old"),
            // An option of a later server, which this page cannot explain.
            item("kb_failed", "odd", "retry_slowly", ranking),
          ],
        },
      }),
    );

    // The option is one for the whole copy, so the question is asked once, after the list.
    expect(boxes()).toEqual([
      "Leave it behind, legacy",
      "Leave it behind, lost",
      null,
    ]);
    const option = screen.getByRole("checkbox", {
      name: /^Accept the new ranking for every knowledge base listed with it\./,
    });
    expect(option).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Leave it behind, legacy" }),
    ).toBeChecked();
    const lost = screen.getByRole("checkbox", {
      name: "Leave it behind, lost",
    });
    expect(lost).not.toBeChecked();
    // Who left the first one behind stands in its own row, and nowhere else.
    const [, , legacy] = screen.getAllByRole("listitem");
    expect(
      within(legacy).getByText(/^Accepted by alice on /),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/^Accepted by /)).toHaveLength(1);
    // Leaving one behind settles it at once, so nothing waits for another copy.
    expect(
      screen.queryByText("This applies to the next copy."),
    ).not.toBeInTheDocument();

    await userEvent.click(option);
    await userEvent.click(lost);

    const decisions = expect.stringContaining("decisions");
    expect(post).toHaveBeenNthCalledWith(1, decisions, {
      step: "copy_knowledge_bases",
      kind: "accept_ranking_change",
      subject: null,
      run_id: null,
    });
    // The choice that did not go through says so under its own box, and under no other.
    const failed = await screen.findAllByText(
      "Something went wrong. Try again.",
    );
    expect(failed).toHaveLength(1);
    expect(screen.getAllByRole("listitem")[3]).toContainElement(failed[0]);
    // An acceptance names the copy whose list the item is in, so a page that is behind accepts nothing by mistake.
    expect(post).toHaveBeenNthCalledWith(2, decisions, {
      step: "copy_knowledge_bases",
      kind: "leave_behind",
      subject: "id-lost",
      run_id: "run-3",
    });

    // Taking one back names the same copy.
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Leave it behind, legacy" }),
    );
    expect(withdrawn).toHaveBeenCalledWith(decisions, {
      data: {
        step: "copy_knowledge_bases",
        kind: "leave_behind",
        subject: "id-legacy",
        run_id: "run-3",
      },
    });
  });

  it("accepts a file with the decision the server gave it, and none it has no words for", async () => {
    const post = jest.spyOn(api, "post").mockRejectedValue(unreachable());
    const files = { files: true };
    show(
      panel("copy_files", {
        report: {
          ok: false,
          counts: { copied: 9, failed: 5 },
          attention: [
            item("file_conflict", "cat.txt", "keep_bucket_file", files),
            item(
              "no_source_bytes",
              "gone.txt",
              "accept_missing_attachment",
              files,
            ),
            item("bad_name", "odd.txt", undefined, files),
            // The page has no table of its own: a code the server offers nothing for gets nothing.
            item("file_conflict", "dog.txt", undefined, files),
            // A decision of a later server, which this page cannot explain.
            item("verify_failed", "new.txt", "accept_unverified", files),
          ],
        },
      }),
    );

    expect(boxes()).toEqual([
      "Keep the bucket's file, cat.txt",
      "Move without this file, gone.txt",
    ]);
    // The check in the first step may have asked about a file like this already. The step says why it asks again.
    expect(
      screen.getByText(
        "Accepting a finding in 'Check this instance' lets the move go on. This copy names each one it left, so each is accepted here, for this copy only.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Keep the bucket's file, cat.txt" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Move without this file, gone.txt",
      }),
    );

    const decisions = expect.stringContaining("decisions");
    expect(post).toHaveBeenNthCalledWith(1, decisions, {
      step: "copy_files",
      kind: "keep_bucket_file",
      subject: "u-1/cat.txt",
      run_id: "run-3",
    });
    expect(post).toHaveBeenNthCalledWith(2, decisions, {
      step: "copy_files",
      kind: "accept_missing_attachment",
      subject: "u-1/gone.txt",
      run_id: "run-3",
    });
  });

  it("says a choice the server refused for another reason did not go through", async () => {
    jest
      .spyOn(api, "post")
      .mockRejectedValue(refused(400, { code: "unknown_decision" }));
    show(
      panel("copy_files", {
        report: {
          ok: false,
          counts: { copied: 2, failed: 1 },
          attention: [
            item("file_conflict", "cat.txt", "keep_bucket_file", {
              files: true,
            }),
          ],
        },
      }),
    );

    await userEvent.click(screen.getByRole("checkbox"));

    expect(
      await screen.findByText("Something went wrong. Try again."),
    ).toBeInTheDocument();
    // Only a copy made over since gets the line about a new list.
    expect(
      screen.queryByText(/made again in the meantime/),
    ).not.toBeInTheDocument();
  });

  it("says nothing about accepting when the only decision on offer is one it has no words for", () => {
    show(
      panel("copy_files", {
        report: {
          ok: false,
          counts: { copied: 2, failed: 1 },
          attention: [
            item("verify_failed", "new.txt", "accept_unverified", {
              files: true,
            }),
          ],
        },
      }),
    );

    expect(screen.getByRole("listitem")).toHaveTextContent("new.txt");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(note()).not.toBeInTheDocument();
  });

  it("offers an option after a test run, and no acceptance of what no copy has left yet", () => {
    show(
      panel(
        "copy_knowledge_bases",
        {
          dry_run: true,
          report: {
            ok: false,
            counts: { would_relocate: 1, failed: 2 },
            attention: [
              item("kb_backend_missing", "legacy", "leave_behind"),
              // The option was taken before this test run, so the server says it is in effect.
              item("kb_metric_change", "notes", "accept_ranking_change", {
                option: true,
                made: true,
              }),
            ],
          },
        },
        "current",
      ),
    );

    // An option changes the next run, which may be the copy. An item is accepted in the copy that left it.
    expect(boxes()).toEqual([null]);
    expect(note()).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /^Accept the new ranking/ }),
    ).toBeChecked();
    expect(
      screen.getByText("This applies to the next copy."),
    ).toBeInTheDocument();
  });

  it("says why nothing can be accepted one by one when more failed than the list holds, and still asks about an option", () => {
    show(
      panel("copy_knowledge_bases", {
        report: {
          ok: false,
          counts: { failed: 250 },
          attention: [
            // The server offers no acceptance on a list it cut short: it cannot tell which of the others were accepted.
            item("kb_backend_missing", "legacy"),
            // An option holds for all of them, the ones the list does not show included, so it is still on offer.
            item("kb_metric_change", "notes", "accept_ranking_change", {
              option: true,
            }),
          ],
        },
      }),
    );

    expect(boxes()).toEqual([null]);
    expect(
      screen.getByRole("checkbox", { name: /^Accept the new ranking/ }),
    ).not.toBeChecked();
    expect(note()).not.toBeInTheDocument();
    expect(screen.getByText("Showing the first 2 of 250.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "More were not copied than this list holds, so they can't be accepted one by one.",
      ),
    ).toBeInTheDocument();
  });
});
