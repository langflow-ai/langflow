import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SafetySummary } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import ModelComparison from "../components/ModelComparison";
import { variantRun } from "./comparisonFixtures";

const safety = (safe: number, jailbreak: number): SafetySummary => ({
  checks: ["off_topic", "jailbreak"],
  judged: 10,
  skipped: 0,
  safe,
  rates: { off_topic: 0, jailbreak },
  attacks: { total: 4, resisted: Math.round(4 * (1 - jailbreak)) },
});

const RUNS = [
  variantRun({ index: 0, passed: 7, cost: 0.04, safety: safety(0.7, 0.3) }),
  variantRun({ index: 1, passed: 9, cost: 0.01, safety: safety(1, 0) }),
  variantRun({ index: 2, status: "running", safety: safety(0.9, 0.1) }),
];

describe("ModelComparison", () => {
  it("should name the winners and rank the finished versions first", () => {
    render(
      <ModelComparison
        runs={RUNS}
        comparisonId="cmp-1"
        selectedRunId="run-1"
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("comparison-most-accurate")).toHaveTextContent(
      "gpt-4o-mini",
    );
    expect(screen.getByTestId("comparison-cheapest")).toHaveTextContent(
      "gpt-4o-mini",
    );
    const rows = screen.getAllByTestId("comparison-row");
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("gpt-4o-mini"),
      expect.stringContaining("Flow models"),
      expect.stringContaining("claude-haiku-5-5"),
    ]);
    expect(rows[0]).toHaveAttribute("aria-selected", "true");
    expect(rows[0]).toHaveTextContent("Cheapest");
    expect(rows[1]).toHaveTextContent("$0.0400");
    expect(rows[1]).toHaveTextContent("4× min");
    expect(within(rows[2]).getByTestId("run-status-running")).toBeVisible();
  });

  it("should name every version in a tie instead of crowning the tie-break winner", () => {
    render(
      <ModelComparison
        runs={[0, 1, 2].map((index) =>
          variantRun({ index, passed: 10, cost: 0.01 * (index + 1) }),
        )}
        comparisonId="cmp-1"
        selectedRunId={null}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("comparison-most-accurate")).toHaveTextContent(
      "3 versions tied",
    );
    const rows = screen.getAllByTestId("comparison-row");
    expect(rows[1]).toHaveTextContent("Tie");
    expect(rows[1]).not.toHaveTextContent("≈ #1");
    expect(screen.getByText(/the same pass rate as #1/)).toBeVisible();
  });

  it("should compare the safety checks of every version that has them", () => {
    render(
      <ModelComparison
        runs={RUNS}
        comparisonId="cmp-1"
        selectedRunId={null}
        onSelect={jest.fn()}
      />,
    );

    const table = screen.getByTestId("comparison-safety");
    expect(within(table).getAllByTestId("comparison-safety-row")).toHaveLength(
      3,
    );
    expect(table).toHaveTextContent("Jailbreak");
  });

  it("should leave the safety table out when no version ran safety checks", () => {
    render(
      <ModelComparison
        runs={[variantRun({ index: 0 }), variantRun({ index: 1 })]}
        comparisonId="cmp-1"
        selectedRunId={null}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.queryByTestId("comparison-safety")).not.toBeInTheDocument();
  });

  it("should open a version's results from its row", async () => {
    const onSelect = jest.fn();
    render(
      <ModelComparison
        runs={RUNS}
        comparisonId="cmp-1"
        selectedRunId={null}
        onSelect={onSelect}
      />,
    );

    await userEvent.click(
      within(screen.getAllByTestId("comparison-row")[1]).getByRole("button"),
    );

    expect(onSelect).toHaveBeenCalledWith("run-0");
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(
      <ModelComparison
        runs={RUNS}
        comparisonId="cmp-1"
        selectedRunId="run-1"
        onSelect={jest.fn()}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
