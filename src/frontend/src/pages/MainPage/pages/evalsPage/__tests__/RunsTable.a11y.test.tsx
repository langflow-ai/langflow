import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import RunsTable from "../components/RunsTable";

function run(overrides: Partial<EvaluationRun>): EvaluationRun {
  return {
    id: "run-1",
    evaluation_id: "eval-1",
    status: "completed",
    flow_id: "flow-1",
    flow_name: "Support",
    flow_version_id: "v-1",
    flow_version_number: 3,
    flow_version_source: "latest",
    dataset_id: "ds-1",
    dataset_name: "support-qa",
    dataset_revision: 1,
    config: { scorers: [], pass_threshold: 0.5, output_vertex_id: "out" },
    total_items: 10,
    completed_items: 10,
    failed_items: 0,
    passed_items: 8,
    summary: {
      scores: {},
      duration_ms: { mean: 100, p50: 100, p90: 120 },
      tokens: { flow: 1380, judge: 0, total: 1380 },
      cost_usd: { flow: null, judge: null, total: null, complete: false },
      pass_rate: 0.8,
      rows: { total: 10, errored: 0, decided: 10 },
    },
    estimate: null,
    error: null,
    started_at: "2026-10-26T10:00:00Z",
    finished_at: "2026-10-26T10:01:00Z",
    created_at: "2026-10-26T10:00:00Z",
    ...overrides,
  };
}

const RUNS: EvaluationRun[] = [
  run({ id: "run-2" }),
  run({
    id: "run-1",
    flow_version_source: "history",
    flow_version_number: 2,
    summary: {
      ...run({}).summary!,
      tokens: { flow: 1000, judge: 0, total: 1000 },
    },
    created_at: "2026-10-25T10:00:00Z",
  }),
];

describe("RunsTable", () => {
  it("should show the version each run used and the token change against the previous run", () => {
    render(
      <RunsTable runs={RUNS} selectedRunId="run-2" onSelect={jest.fn()} />,
    );
    expect(screen.getByText("Latest → v3")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("(+38%)")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("should select a run from the keyboard", async () => {
    const onSelect = jest.fn();
    render(<RunsTable runs={RUNS} selectedRunId="run-2" onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button", {
      name: /Open the run from/,
    });
    buttons[1].focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("run-1");
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(
      <RunsTable runs={RUNS} selectedRunId="run-2" onSelect={jest.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
