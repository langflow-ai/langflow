import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ScorerType } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import ScorerFields from "../ScorerFields";

// The judge's model list loads providers; only the scorer cards are under test.
jest.mock("../useModelOptions", () => ({
  useModelOptions: () => ({ options: [], ready: true }),
}));

function renderScorers(selected: ScorerType[]) {
  const onToggle = jest.fn();
  const view = render(
    <ScorerFields
      flowId="flow-1"
      selected={new Set(selected)}
      onToggle={onToggle}
      judgeModel={[]}
      onJudgeModel={jest.fn()}
      rubric=""
      onRubric={jest.fn()}
      judgeLimits={{
        maxOutputTokens: "600",
        maxRunOutputTokens: "8192",
        stopOnOutputLimit: true,
      }}
      onJudgeLimits={jest.fn()}
      judgeRowBudgetInvalid={false}
      judgeRunBudgetInvalid={false}
      safetyChecks={[]}
      onSafetyChecks={jest.fn()}
    />,
  );
  return { ...view, onToggle };
}

describe("ScorerFields", () => {
  it("should_explain_each_scorer_behind_an_info_button_instead_of_a_line_below", () => {
    renderScorers(["exact_match"]);

    expect(
      screen.getByRole("button", { name: "About Contains" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Passes when the answer includes the expected text."),
    ).toBeNull();
  });

  it("should_toggle_the_scorer_but_not_when_its_info_button_is_clicked", async () => {
    const { onToggle } = renderScorers([]);

    await userEvent.click(screen.getByTestId("scorer-contains-info"));
    expect(onToggle).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("checkbox", { name: /Contains/ }));
    expect(onToggle).toHaveBeenCalledWith("contains", true);
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = renderScorers(["exact_match"]);

    expect(await axe(container)).toHaveNoViolations();
  });
});
