import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import DecisionQuestionsComponent from "..";

jest.mock("@/modals/tableModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

const newQuestion = {
  name: "",
  kind: "Choice",
  question: "",
  options: [{ id: "a", label: "Option A" }],
  levels: [{ id: "low", label: "Low" }],
};

const renderQuestions = (value: Record<string, unknown>[]) => {
  const handleOnNewValue = jest.fn();
  const view = render(
    <DecisionQuestionsComponent
      id="questions"
      value={value}
      editNode={false}
      disabled={false}
      columns={[]}
      newQuestion={newQuestion}
      handleOnNewValue={handleOnNewValue}
    />,
  );
  return { ...view, handleOnNewValue };
};

describe("DecisionQuestionsComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderQuestions([newQuestion]);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("appends a copy of the new question when Add question is clicked", () => {
    const { handleOnNewValue } = renderQuestions([newQuestion]);
    fireEvent.click(screen.getByTestId("questions_add"));
    const [[{ value }]] = handleOnNewValue.mock.calls;
    expect(value).toEqual([newQuestion, newQuestion]);
    expect(value[1]).not.toBe(newQuestion);
  });

  it("keeps the last question and removes any other", () => {
    const { handleOnNewValue, rerender } = renderQuestions([newQuestion]);
    expect(screen.getByTestId("questions_remove_0")).toBeDisabled();

    const urgent = { ...newQuestion, name: "urgent", kind: "Boolean" };
    rerender(
      <DecisionQuestionsComponent
        id="questions"
        value={[newQuestion, urgent]}
        editNode={false}
        disabled={false}
        newQuestion={newQuestion}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.click(screen.getByTestId("questions_remove_0"));
    expect(handleOnNewValue).toHaveBeenLastCalledWith({ value: [urgent] });
  });

  it("shows each question only the fields its Decision Type uses", () => {
    renderQuestions([
      newQuestion,
      { ...newQuestion, kind: "Boolean" },
      { ...newQuestion, kind: "Score" },
    ]);
    expect(screen.getByText("Edit options")).toBeInTheDocument();
    expect(screen.getByText("Edit levels")).toBeInTheDocument();
    expect(screen.getAllByLabelText("What Yes means (optional)")).toHaveLength(
      1,
    );
  });

  it("edits only the question that changed", () => {
    const second = { ...newQuestion, name: "urgent" };
    const { handleOnNewValue } = renderQuestions([newQuestion, second]);
    fireEvent.change(screen.getByLabelText("Question 1 text"), {
      target: { value: "Which team?" },
    });
    expect(handleOnNewValue).toHaveBeenLastCalledWith({
      value: [{ ...newQuestion, question: "Which team?" }, second],
    });
  });
});
