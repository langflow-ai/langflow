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
  acceptable_findings: [],
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
