import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import EvaluateStepper from "../EvaluateStepper";

const STEPS = [
  { key: "setup", label: "Setup" },
  { key: "scoring", label: "Scoring" },
  { key: "review", label: "Review" },
];

describe("EvaluateStepper", () => {
  it("should mark the current step and let the user reopen only finished ones", async () => {
    const onSelect = jest.fn();
    render(<EvaluateStepper steps={STEPS} current={1} onSelect={onSelect} />);

    expect(screen.getByTestId("evaluate-step-scoring")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(
      screen.getByTestId("evaluate-step-review").closest("button"),
    ).toBeNull();
    await userEvent.click(screen.getByTestId("evaluate-step-setup"));

    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(
      <EvaluateStepper steps={STEPS} current={2} onSelect={jest.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
