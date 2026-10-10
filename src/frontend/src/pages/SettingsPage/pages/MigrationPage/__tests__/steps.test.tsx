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
    expect(screen.getByText(/needs the pgvector extension/)).toBeVisible();
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
