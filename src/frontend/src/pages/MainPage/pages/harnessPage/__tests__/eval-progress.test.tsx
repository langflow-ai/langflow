import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api } from "@/controllers/API/api";
import {
  type EvalRun,
  useEvalRuns,
} from "@/controllers/API/queries/folders/use-eval-suite";
import { EvalRuns } from "../components/eval-runs";

jest.mock("@/controllers/API/api", () => ({
  api: { post: jest.fn(), get: jest.fn() },
}));
jest.mock("@/contexts", () => ({
  queryClient: new (jest.requireActual("@tanstack/react-query").QueryClient)(),
}));
jest.mock("@/controllers/API/agui/run-flow-bridge", () => ({
  consumeBackgroundEvents: jest.fn(),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => <span>{children}</span>,
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));

const paused: EvalRun = {
  id: "evaluation",
  status: "suspended",
  created_at: "2026-09-16T12:00:00Z",
  passed: false,
  candidate_digest: "a".repeat(64),
  scorer_digest: "b".repeat(64),
  suite_revision: "revision",
  result: {
    suite: {
      workflow_id: "root",
      candidate_digest: "a".repeat(64),
      scorer: null,
      cases: [],
    },
    cases: [],
    complete: false,
  },
  pending_approval: {
    job_id: "child",
    phase: "candidate",
    case_id: "research",
    request: {
      request_id: "approval-1",
      kind: "tool_approval",
      prompt: "Approve evidence search?",
      options: [
        { action_id: "approve", label: "Approve" },
        { action_id: "reject", label: "Reject" },
      ],
      allowed_decisions: ["approve", "reject"],
    },
  },
};

function show(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {ui}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  jest.clearAllMocks();
  (api.post as jest.Mock).mockResolvedValue({ data: {} });
});

test("a restored approval sends the existing child and request IDs, once", async () => {
  show(<EvalRuns projectId="suite" runs={[paused]} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() =>
    expect(api.post).toHaveBeenCalledWith("/api/v2/workflows/child/resume", {
      request_id: "approval-1",
      decision: { action_id: "approve", values: {} },
    }),
  );
  expect(screen.getByRole("button", { name: /Approve/ })).toBeDisabled();
  expect(api.post).toHaveBeenCalledTimes(1);
});

test("cancellation targets the evaluation and hides further approval actions", async () => {
  show(<EvalRuns projectId="suite" runs={[paused]} />);
  fireEvent.click(screen.getByRole("button", { name: /Cancel run/i }));
  await waitFor(() =>
    expect(api.post).toHaveBeenCalledWith(
      "/api/v1/projects/suite/evaluations/runs/evaluation/cancel",
    ),
  );
  expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
});

function History() {
  const query = useEvalRuns("suite", false);
  return <span>{query.data?.[0]?.status}</span>;
}
test("opening persisted active history keeps polling until completion", async () => {
  (api.get as jest.Mock)
    .mockResolvedValueOnce({ data: [paused] })
    .mockResolvedValue({ data: [{ ...paused, status: "completed" }] });
  show(<History />);
  await screen.findByText("suspended");
  await screen.findByText("completed", {}, { timeout: 3500 });
});

test("an unconfirmed decision shows an error and permits an explicit retry", async () => {
  (api.post as jest.Mock).mockRejectedValueOnce(new Error("Network failure"));
  const withNote: EvalRun = {
    ...paused,
    pending_approval: {
      ...paused.pending_approval!,
      request: {
        ...paused.pending_approval!.request,
        schema: [{ name: "note", required: true }],
      },
    },
  };
  show(<EvalRuns projectId="suite" runs={[withNote]} />);
  fireEvent.change(screen.getByTestId("human-input-field-note"), {
    target: { value: "Reviewed the original evidence" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await screen.findByText(/Approval was not confirmed/);
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("human-input-field-note")).toHaveValue(
    "Reviewed the original evidence",
  );
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));
});

test("a stale approval stays locked while the persisted status refreshes", async () => {
  (api.post as jest.Mock).mockRejectedValueOnce({ response: { status: 409 } });
  show(<EvalRuns projectId="suite" runs={[paused]} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await screen.findByText(/approval has already been resolved/);
  expect(screen.getByRole("button", { name: /Approve/ })).toBeDisabled();
  expect(api.post).toHaveBeenCalledTimes(1);
});
