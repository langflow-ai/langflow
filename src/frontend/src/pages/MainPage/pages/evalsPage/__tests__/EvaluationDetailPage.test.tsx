import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import EvaluationDetailPage from "../EvaluationDetailPage";
import { variantRun } from "./comparisonFixtures";

type Query<T> = { data?: T; isError?: boolean; refetch?: jest.Mock };

const mockRefetchRuns = jest.fn();
let mockEvaluation: Query<{ id: string; name: string }> = {};
let mockRuns: Query<{ items: EvaluationRun[] }> = {};
let mockSelectedRun: EvaluationRun | undefined;
const mockRunQuery = jest.fn();
const mockViews = jest.fn();

jest.mock("@/controllers/API/queries/evals/use-evaluations", () => ({
  exportUrl: () => "",
  useCancelEvaluationRun: () => ({ mutate: jest.fn(), isPending: false }),
  useGetEvaluation: () => mockEvaluation,
  useGetEvaluationRuns: (params: { comparisonId?: string }) =>
    params.comparisonId
      ? { data: undefined }
      : { ...mockRuns, refetch: mockRefetchRuns },
  useGetEvaluationRun: (params: { runId: string }) => {
    mockRunQuery(params.runId);
    return { data: mockSelectedRun };
  },
}));
jest.mock("../hooks/use-rerun", () => ({
  useRerun: () => ({ canRerun: false, request: jest.fn(), cancel: jest.fn() }),
}));
jest.mock("../components/EvalsPageShell", () => ({
  __esModule: true,
  default: ({ title, children }: { title: ReactNode; children: ReactNode }) => (
    <main>
      <h1>{title}</h1>
      {children}
    </main>
  ),
}));
jest.mock("../components/RunViews", () => ({
  __esModule: true,
  isRunView: (value: unknown) =>
    value === "runs" || value === "results" || value === "comparison",
  default: (props: { view: string; selectedRun?: EvaluationRun }) => {
    mockViews(props);
    return <div data-testid="run-views">{props.view}</div>;
  },
}));

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/assets/evaluations/eval-1${search}`]}>
      <Routes>
        <Route
          path="/assets/evaluations/:evaluationId"
          element={<EvaluationDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

const plainRun = (id: string, completed = 0): EvaluationRun => {
  const run = variantRun({ index: 0 });
  delete run.config.comparison;
  return { ...run, id, status: "running", completed_items: completed };
};

describe("EvaluationDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEvaluation = { data: { id: "eval-1", name: "My evaluation" } };
    mockRuns = { data: { items: [plainRun("run-a"), plainRun("run-b")] } };
    mockSelectedRun = mockRuns.data?.items[0];
  });

  it("should_say_the_runs_could_not_load_instead_of_spinning_forever", () => {
    mockRuns = { isError: true };

    renderAt("");

    expect(
      screen.getByTestId("evaluation-runs-load-error"),
    ).toBeInTheDocument();
  });

  it("should_open_the_runs_view_and_the_newest_run_without_url_state", () => {
    renderAt("");

    expect(screen.getByTestId("run-views")).toHaveTextContent("runs");
    expect(mockRunQuery).toHaveBeenLastCalledWith("run-a");
  });

  it("should_honor_the_run_and_view_in_the_url", () => {
    renderAt("?run=run-b&view=results");

    expect(screen.getByTestId("run-views")).toHaveTextContent("results");
    expect(mockRunQuery).toHaveBeenLastCalledWith("run-b");
  });

  it("should_fall_back_to_runs_when_the_url_asks_for_a_comparison_the_run_lacks", () => {
    renderAt("?view=comparison");

    expect(screen.getByTestId("run-views")).toHaveTextContent("runs");
  });

  it("should_refresh_the_runs_list_when_the_selected_run_moves_forward", () => {
    const view = renderAt("");
    expect(mockRefetchRuns).not.toHaveBeenCalled();

    mockSelectedRun = plainRun("run-a", 1);
    view.rerender(
      <MemoryRouter initialEntries={["/assets/evaluations/eval-1"]}>
        <Routes>
          <Route
            path="/assets/evaluations/:evaluationId"
            element={<EvaluationDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(mockRefetchRuns).toHaveBeenCalledTimes(1);
  });
});
