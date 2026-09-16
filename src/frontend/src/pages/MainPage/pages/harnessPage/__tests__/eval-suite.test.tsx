import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  comparableRuns,
  type EvalContext,
  type EvalRun,
} from "@/controllers/API/queries/folders/use-eval-suite";
import { EvalRuns } from "../components/eval-runs";
import EvalSuitePage from "../eval-suite-page";

jest.mock("@/controllers/API/api", () => ({ api: { post: jest.fn() } }));
jest.mock("@/controllers/API/queries/flows/use-post-add-flow", () => ({
  usePostAddFlow: () => ({ mutateAsync: jest.fn() }),
}));
const mockSave = jest.fn();
const mockRun = jest.fn();
const mockRefetch = jest.fn();
jest.mock("@/controllers/API/queries/folders/use-patch-folders", () => ({
  usePatchFolders: () => ({ mutateAsync: mockSave, isPending: false }),
}));
jest.mock("@/controllers/API/queries/folders/use-eval-suite", () => ({
  ...jest.requireActual("@/controllers/API/queries/folders/use-eval-suite"),
  useEvalSuite: () => ({ data: mockContext, refetch: mockRefetch }),
  useEvalRuns: () => ({ data: [], refetch: mockRefetch }),
  useRunEvalSuite: () => ({ mutateAsync: mockRun, isPending: false }),
}));

const mockContext: EvalContext = {
  revision: "reviewed-suite",
  config: {
    workflow_id: "root",
    candidate_digest: "a".repeat(64),
    scorer: {
      flow_id: "scorer",
      node_id: "output",
      output_name: "evaluation",
      revision: "reviewed",
      version_id: "saved-version",
    },
    cases: [
      {
        id: "case",
        name: "Research",
        input: "Find evidence",
        reference: "Reference",
        minimum_score: 1,
        require_sourced_artifact: true,
        require_supported_claims: true,
        expected_policy: "compliant",
        max_latency_ms: null,
        max_cost_usd: null,
      },
    ],
  },
  targets: [
    {
      workflow_id: "root",
      name: "Research harness",
      candidate_digest: "a".repeat(64),
    },
  ],
  scorers: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  mockRun.mockResolvedValue({});
});

test("runs the saved revision and digest, but requires saving case edits first", async () => {
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Run suite/i }));
  await waitFor(() =>
    expect(mockRun).toHaveBeenCalledWith(
      expect.objectContaining({
        expected_revision: "reviewed-suite",
        expected_candidate_digest: "a".repeat(64),
        run_id: expect.any(String),
      }),
    ),
  );
  fireEvent.change(screen.getByLabelText("Reference answer or rubric"), {
    target: { value: "Changed rubric" },
  });
  expect(screen.getByRole("button", { name: /Run suite/i })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: /Create scorer flow/i }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /Save suite/i }));
  await waitFor(() =>
    expect(mockSave).toHaveBeenCalledWith(
      expect.objectContaining({
        folderId: "suite",
        data: {
          project_config: expect.objectContaining({
            cases: [expect.objectContaining({ reference: "Changed rubric" })],
          }),
        },
      }),
    ),
  );
});

test("unknown cost and lost responses are explicit and never cause automatic reruns", async () => {
  mockRun.mockRejectedValue(new Error("Network failure"));
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Run suite/i }));
  await screen.findByText(/Check this submission/);
  expect(screen.getByRole("button", { name: /Run suite/i })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /Refresh status/i }));
  expect(mockRun).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Cost budget (USD, optional)"), {
    target: { value: "1" },
  });
  expect(
    screen.getByText(/Measured cost is not available/),
  ).toBeInTheDocument();
});

function record(id: string, patch: Partial<EvalRun> = {}): EvalRun {
  return {
    id,
    status: "completed",
    created_at: "2026-09-16T12:00:00Z",
    candidate_digest: "a".repeat(64),
    scorer_digest: "scorer-digest",
    suite_revision: "suite-revision",
    passed: false,
    result: {
      suite: mockContext.config,
      cases: [
        {
          case_id: "case",
          passed: false,
          failures: ["claims_not_supported"],
          latency_ms: 15,
          cost_usd: null,
          workflow_job_id: "workflow-run",
          scorer_job_id: "scorer-run",
          verdict: {
            score: 1,
            reason: "Unsupported claim",
            claim_support: "unsupported",
            policy: "compliant",
          },
          output: {},
        },
      ],
      complete: true,
    },
    ...patch,
  };
}

test("only compares complete runs with identical evaluation requirements and scorer", () => {
  const first = record("first");
  expect(
    comparableRuns(
      first,
      record("second", { candidate_digest: "b".repeat(64) }),
    ),
  ).toBe(true);
  for (const patch of [
    { suite_revision: "different" },
    { scorer_digest: "different" },
    { status: "timed_out" },
    { result: null },
  ]) {
    expect(comparableRuns(first, record("second", patch))).toBe(false);
  }
  render(
    <EvalRuns
      projectId="suite"
      runs={[first, record("second", { suite_revision: "different" })]}
    />,
  );
  expect(
    screen.getByText("Claim support was not established"),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Compare score with"), {
    target: { value: "second" },
  });
  expect(screen.getByText(/These runs cannot be compared/)).toBeInTheDocument();
});
