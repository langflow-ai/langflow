import { render, screen } from "@testing-library/react";
import RunViews from "../components/RunViews";
import { variantRun } from "./comparisonFixtures";

// The views are what is under test, not the grid and charts inside them.
jest.mock("../components/RunResults", () => ({
  __esModule: true,
  default: () => <div data-testid="run-results" />,
}));
jest.mock("../components/ModelComparison", () => ({
  __esModule: true,
  default: () => <div data-testid="model-comparison" />,
}));

const plain = () => {
  const run = variantRun({ index: 0 });
  delete run.config.comparison;
  return run;
};

describe("RunViews", () => {
  it("should order the views runs, results, comparison", () => {
    const runs = [variantRun({ index: 0 }), variantRun({ index: 1 })];
    render(
      <RunViews
        runs={runs}
        selectedRun={runs[0]}
        comparisonRuns={runs}
        view="comparison"
        onView={jest.fn()}
        onOpenRun={jest.fn()}
      />,
    );

    expect(
      screen.getAllByRole("tab").map((tab) => tab.getAttribute("data-testid")),
    ).toEqual([
      "detail-tab-runs",
      "detail-tab-results",
      "detail-tab-comparison",
    ]);
    expect(screen.getByTestId("model-comparison")).toBeInTheDocument();
  });

  it("should leave the comparison view out for a run that is not in one", () => {
    const run = plain();
    render(
      <RunViews
        runs={[run]}
        selectedRun={run}
        comparisonRuns={[]}
        view="results"
        onView={jest.fn()}
        onOpenRun={jest.fn()}
      />,
    );

    expect(
      screen.queryByTestId("detail-tab-comparison"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("version-switcher")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-results")).toBeInTheDocument();
  });

  it("should switch the results between a comparison's versions", () => {
    const runs = [variantRun({ index: 0 }), variantRun({ index: 1 })];
    render(
      <RunViews
        runs={runs}
        selectedRun={runs[1]}
        comparisonRuns={runs}
        view="results"
        onView={jest.fn()}
        onOpenRun={jest.fn()}
      />,
    );

    const versions = screen
      .getByTestId("version-switcher")
      .querySelectorAll("button");
    expect(
      [...versions].map((button) => button.getAttribute("aria-pressed")),
    ).toEqual(["false", "true"]);
  });
});
