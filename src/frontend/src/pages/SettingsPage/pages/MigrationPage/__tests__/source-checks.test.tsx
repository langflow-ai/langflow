import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api } from "@/controllers/API/api";
import {
  type MigrationState,
  runSourceChecks,
  useMigrationQuery,
} from "@/controllers/API/queries/migration";
import { CheckStep } from "../CheckStep";

const migration: MigrationState = {
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: false },
  },
  record: {
    target: { version: "1.13.0" },
    steps: {
      check_source: {
        status: "done",
        started_by: "admin",
        started_at: "2026-10-06T12:00:00Z",
        finished_at: "2026-10-06T12:01:00Z",
        target_version: "1.13.0",
        exit_code: 0,
        report: { ok: true, checks: [] },
        error: null,
      },
    },
    accepted_findings: [],
  },
  steps: [{ id: "check_source", state: "done" }],
  blocking_findings: [],
  acceptable_checks: [],
};

function Subject() {
  const { data } = useMigrationQuery();
  return data ? <CheckStep migration={data} /> : null;
}

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  jest.restoreAllMocks();
});

it("shows a failed new request when transport fails before a run starts", async () => {
  jest.spyOn(api, "get").mockResolvedValue({ data: migration });
  global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <Subject />
    </QueryClientProvider>,
  );

  await screen.findByTestId("migration-checks-summary");
  fireEvent.click(screen.getByTestId("migration-run-checks"));

  await screen.findByText("The check couldn't finish.");
  expect(screen.queryByTestId("migration-checks-summary")).toBeNull();
  await waitFor(() =>
    expect(screen.getByTestId("migration-run-checks")).toBeEnabled(),
  );
});

it("does not report a deliberate stop as a transport failure", async () => {
  const controller = new AbortController();
  global.fetch = jest.fn().mockImplementation(() => {
    controller.abort();
    return Promise.reject(new DOMException("Stopped", "AbortError"));
  });

  await expect(
    runSourceChecks({
      targetVersion: "1.13.0",
      controller,
      onEvent: jest.fn(),
    }),
  ).resolves.toBeUndefined();
});

// On the page this check never fails. Its warning has to be dealt with before the pause, so the row names no
// later step.
it("says what to do about the 'langflow' account and names no later step", async () => {
  const warned = {
    ...migration,
    record: {
      ...migration.record,
      steps: {
        check_source: {
          ...migration.record.steps.check_source,
          report: {
            ok: true,
            checks: [
              {
                name: "default superuser",
                status: "warn",
                summary: "'langflow' has signed in and AUTO_LOGIN is on",
                problems: [],
              },
              {
                name: "role assignments",
                status: "warn",
                summary: "1 role assignment moves with the database",
                problems: [],
              },
            ],
          },
        },
      },
    },
  };
  jest.spyOn(api, "get").mockResolvedValue({ data: warned });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Subject />
    </QueryClientProvider>,
  );

  const row = await screen.findByTestId("migration-check-default superuser");
  expect(row).toHaveTextContent("Before you pause changes");
  expect(row).not.toHaveTextContent("Handled in");
  // A warning that a later step deals with still names it.
  expect(
    screen.getByTestId("migration-check-role assignments"),
  ).toHaveTextContent("Handled in: Start the new instance");
});

it("offers no other check and no other word about one once the new instance has started", async () => {
  const withdrawn = jest.spyOn(api, "delete").mockResolvedValue({ data: {} });
  const accepted = jest.spyOn(api, "post").mockResolvedValue({ data: {} });
  const failing = {
    name: "source: files",
    status: "fail" as const,
    summary: "1 of 2 file rows point at bytes storage does not hold",
    problems: [],
  };
  const started: MigrationState = {
    ...migration,
    record: {
      ...migration.record,
      steps: {
        check_source: {
          ...migration.record.steps.check_source,
          report: { ok: false, checks: [failing] },
        } as MigrationState["record"]["steps"]["check_source"],
      },
      accepted_findings: [
        {
          name: failing.name,
          summary: failing.summary,
          accepted_by: "alice",
          accepted_at: "2026-10-06T12:02:00Z",
        },
      ],
    },
    steps: [
      { id: "check_source", state: "done" },
      { id: "start_target", state: "done" },
    ],
    acceptable_checks: [failing.name],
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CheckStep migration={started} />
    </QueryClientProvider>,
  );

  // What the last check found stays to read, with who accepted it.
  expect(screen.getByText(/^Accepted by alice on /)).toBeInTheDocument();
  // The server takes no other check from here on, so the page has no version field and no button for one.
  expect(screen.queryByTestId("migration-run-checks")).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
  // The new instance runs on what was accepted, so the acceptance stays as it was given.
  const box = screen.getByRole("checkbox");
  expect(box).toBeChecked();
  expect(box).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(box);
  await waitFor(() => expect(box).toBeChecked());
  expect(withdrawn).not.toHaveBeenCalled();
  expect(accepted).not.toHaveBeenCalled();
});
