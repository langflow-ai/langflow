import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { api } from "@/controllers/API/api";
import {
  comparableRuns,
  type EvalContext,
  type EvalRun,
} from "@/controllers/API/queries/folders/use-eval-suite";
import { EvalRuns } from "../components/eval-runs";
import EvalSuitePage from "../eval-suite-page";
import { selectOption } from "./select-option";

jest.mock("@/controllers/API/api", () => ({ api: { post: jest.fn() } }));
const mockCreateFlow = jest.fn();
jest.mock("@/controllers/API/queries/flows/use-post-add-flow", () => ({
  usePostAddFlow: () => ({ mutateAsync: mockCreateFlow }),
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

const initialContext: EvalContext = {
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
let mockContext: EvalContext;

beforeEach(() => {
  jest.resetAllMocks();
  jest.mocked(ResizeObserver).mockImplementation(() => ({
    observe: jest.fn(),
    unobserve: jest.fn(),
    disconnect: jest.fn(),
  }));
  mockContext = JSON.parse(JSON.stringify(initialContext));
  mockRun.mockResolvedValue({});
  mockRefetch.mockImplementation(async () => ({
    data: mockContext,
    isError: false,
  }));
});

test.each([
  ["Minimum score (0–1)", "2", "0.8", /score from 0 to 1/i],
  ["Minimum score (0–1)", "", "0.8", /score from 0 to 1/i],
  [
    "Elapsed budget (ms, including queue and approval)",
    "1.5",
    "2000",
    /whole number from 1 to 3,600,000/i,
  ],
  ["Cost budget (USD, optional)", "0", "1", /cost greater than zero/i],
])(
  "explains invalid %s and enables saving after correction",
  (label, invalid, valid, message) => {
    render(
      <MemoryRouter>
        <EvalSuitePage projectId="suite" />
      </MemoryRouter>,
    );
    const field = screen.getByLabelText(label);
    fireEvent.change(field, { target: { value: invalid } });
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(message);
    expect(screen.getByRole("button", { name: /Save suite/i })).toBeDisabled();
    fireEvent.change(field, { target: { value: valid } });
    expect(field).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByRole("button", { name: /Save suite/i })).toBeEnabled();
  },
);

test("explains required case fields after they are left empty", () => {
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  const field = screen.getByLabelText("Name");
  fireEvent.change(field, { target: { value: " " } });
  fireEvent.blur(field);
  expect(field).toHaveAccessibleDescription("Enter a case name.");
  expect(screen.getByRole("button", { name: /Save suite/i })).toBeDisabled();
  fireEvent.change(field, { target: { value: "Renamed research" } });
  expect(field).toHaveAttribute("aria-invalid", "false");
  expect(screen.getByRole("button", { name: /Save suite/i })).toBeEnabled();
});

test("keeps the form locked until a successful save refresh completes", async () => {
  let finishRefresh!: (value: { data: EvalContext; isError: false }) => void;
  mockRefetch.mockImplementation(
    () =>
      new Promise((resolve) => {
        finishRefresh = resolve;
      }),
  );
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("Reference answer or rubric"), {
    target: { value: "Saved rubric" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Save suite/i }));
  await waitFor(() => expect(mockRefetch).toHaveBeenCalled());
  expect(screen.getByLabelText("Reference answer or rubric")).toBeDisabled();
  expect(screen.getByRole("button", { name: /Save suite/i })).toBeDisabled();
  mockContext.config.cases[0].reference = "Saved rubric";
  await act(async () => finishRefresh({ data: mockContext, isError: false }));
  expect(screen.getByLabelText("Reference answer or rubric")).toHaveValue(
    "Saved rubric",
  );
  expect(screen.getByLabelText("Reference answer or rubric")).toBeEnabled();
});

test("preserves the draft when PATCH succeeds but the refresh fails", async () => {
  mockRefetch.mockResolvedValue({
    data: mockContext,
    isError: true,
    error: new Error("Offline"),
  });
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("Reference answer or rubric"), {
    target: { value: "Keep this rubric" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Save suite/i }));
  await waitFor(() => expect(mockRefetch).toHaveBeenCalled());
  await waitFor(() =>
    expect(screen.getByLabelText("Reference answer or rubric")).toBeEnabled(),
  );
  expect(screen.getByLabelText("Reference answer or rubric")).toHaveValue(
    "Keep this rubric",
  );
  expect(screen.getByRole("button", { name: /Run suite/i })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent(/saved.*refresh/i);
});

test("offers explicit review when only a scorer dependency changed", async () => {
  mockContext.config.scorer!.dependencies = [
    {
      flow_id: "child",
      name: "Judge",
      revision: "old",
      version_id: "child-version",
    },
  ];
  mockContext.scorers = [
    {
      ...mockContext.config.scorer!,
      flow_name: "Scorer",
      display_name: "Evaluation",
      dependencies: [{ flow_id: "child", name: "Judge", revision: "new" }],
    },
  ];
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  expect(screen.getByRole("button", { name: /Run suite/i })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /Use updated scorer/i }));
  expect(screen.getByRole("button", { name: /Run suite/i })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /Save suite/i }));
  await waitFor(() =>
    expect(mockSave).toHaveBeenCalledWith(
      expect.objectContaining({
        data: {
          project_config: expect.objectContaining({
            scorer: expect.objectContaining({
              dependencies: [expect.objectContaining({ revision: "new" })],
            }),
          }),
        },
      }),
    ),
  );
});

test("scorer output names remain distinct even when the flow and node are shared", async () => {
  mockContext.scorers = ["evaluation", "other"].map((output_name) => ({
    ...mockContext.config.scorer!,
    output_name,
    flow_name: "Scorer",
    display_name: output_name,
  }));
  render(
    <MemoryRouter>
      <EvalSuitePage projectId="suite" />
    </MemoryRouter>,
  );
  await selectOption(
    screen.getByRole("combobox", { name: "Scorer" }),
    /Scorer · other/,
  );
  fireEvent.click(screen.getByRole("button", { name: /Save suite/i }));
  await waitFor(() =>
    expect(mockSave).toHaveBeenCalledWith(
      expect.objectContaining({
        data: {
          project_config: expect.objectContaining({
            scorer: expect.objectContaining({ output_name: "other" }),
          }),
        },
      }),
    ),
  );
});

test("finishing scorer creation after leaving cannot redirect the new page", async () => {
  let finishCreation!: (value: { id: string }) => void;
  jest.mocked(api.post).mockResolvedValue({
    data: { name: "Scorer", data: { nodes: [], edges: [] } },
  });
  mockCreateFlow.mockImplementation(
    () =>
      new Promise((resolve) => {
        finishCreation = resolve;
      }),
  );
  function Location() {
    return <output aria-label="Location">{useLocation().pathname}</output>;
  }
  const view = render(
    <MemoryRouter initialEntries={["/suite"]}>
      <EvalSuitePage projectId="suite" />
      <Location />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Create scorer flow/i }));
  await waitFor(() => expect(mockCreateFlow).toHaveBeenCalled());
  view.rerender(
    <MemoryRouter initialEntries={["/suite"]}>
      <p>Another page</p>
      <Location />
    </MemoryRouter>,
  );
  await act(async () => finishCreation({ id: "created-scorer" }));
  expect(screen.getByLabelText("Location")).toHaveTextContent("/suite");
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

test("only compares complete runs with identical evaluation requirements and scorer", async () => {
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
  await selectOption(
    screen.getByRole("combobox", { name: "Compare score with" }),
    /Failed/,
  );
  expect(screen.getByText(/These runs cannot be compared/)).toBeInTheDocument();
});
