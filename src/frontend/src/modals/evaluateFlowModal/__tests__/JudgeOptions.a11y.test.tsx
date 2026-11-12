import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import JudgeLimitFields, { type JudgeLimits } from "../JudgeLimitFields";
import SafetyCheckFields from "../SafetyCheckFields";

const LIMITS: JudgeLimits = {
  maxOutputTokens: "600",
  maxRunOutputTokens: "8192",
  stopOnOutputLimit: true,
};

describe("SafetyCheckFields", () => {
  it("should_summarize_the_chosen_checks_while_collapsed", () => {
    render(
      <SafetyCheckFields
        value={["off_topic", "jailbreak"]}
        onChange={jest.fn()}
      />,
    );

    expect(screen.getByTestId("judge-safety-toggle")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByText("Off topic, Breaks its rules")).toBeInTheDocument();
    expect(screen.queryByTestId("judge-safety-off_topic")).toBeNull();
  });

  it("should_say_none_selected_when_no_check_is_on", () => {
    render(<SafetyCheckFields value={[]} onChange={jest.fn()} />);

    expect(screen.getByText("None selected")).toBeInTheDocument();
  });

  it("should_explain_each_check_behind_a_named_info_button_when_expanded", async () => {
    const onChange = jest.fn();
    const { container } = render(
      <SafetyCheckFields value={[]} onChange={onChange} />,
    );

    await userEvent.click(screen.getByTestId("judge-safety-toggle"));
    await userEvent.click(screen.getByTestId("judge-safety-jailbreak"));

    expect(onChange).toHaveBeenCalledWith(["jailbreak"]);
    expect(
      screen.getByRole("button", { name: "About Leaks personal data" }),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("JudgeLimitFields", () => {
  it("should_move_the_reasoning_note_into_an_info_button_when_the_judge_reasons", async () => {
    const { container } = render(
      <JudgeLimitFields
        value={LIMITS}
        onChange={jest.fn()}
        rowInvalid={false}
        runInvalid={false}
        reasoningModel
      />,
    );

    await userEvent.click(screen.getByTestId("judge-limits-toggle"));

    expect(screen.getByTestId("judge-max-tokens-info")).toHaveAccessibleName(
      "About Max output tokens per row",
    );
    expect(screen.queryByText(/reasons before answering/)).toBeNull();
    expect(screen.getByTestId("judge-stop-on-limit-info")).toBeInTheDocument();
    expect(screen.queryByText(/no more tokens are spent/)).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_show_no_reasoning_info_when_the_judge_does_not_reason", async () => {
    render(
      <JudgeLimitFields
        value={LIMITS}
        onChange={jest.fn()}
        rowInvalid={false}
        runInvalid={false}
        reasoningModel={false}
      />,
    );

    await userEvent.click(screen.getByTestId("judge-limits-toggle"));

    expect(screen.queryByTestId("judge-max-tokens-info")).toBeNull();
  });

  it("should_stay_open_with_the_error_when_a_budget_is_invalid", () => {
    render(
      <JudgeLimitFields
        value={{ ...LIMITS, maxOutputTokens: "0" }}
        onChange={jest.fn()}
        rowInvalid
        runInvalid={false}
        reasoningModel={false}
      />,
    );

    expect(screen.getByTestId("judge-limits-toggle")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByTestId("judge-max-tokens")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});
