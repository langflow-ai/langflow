import { fireEvent, render, screen } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import { axe } from "@/utils/a11y-test";
import DecisionQuestionsComponent from "../decision-questions";

jest.mock("@/modals/tableModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () =>
  jest
    .requireActual("../../__tests__/a11y-mock-helpers")
    .mockGenericIconComponent(),
);

// The real handle needs a React Flow canvas; a marker shows where one is drawn.
jest.mock("../question-handle", () => ({
  __esModule: true,
  default: ({ fieldName }: { fieldName: string }) => (
    <span data-testid={`handle_${fieldName}`} />
  ),
}));

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

  describe("connecting a question", () => {
    const connection = {
      type: "str",
      input_types: ["Message"],
      show: false,
      value: "",
      name: "question_input_1",
      display_name: "Question 1",
    };
    const first = { ...newQuestion, id: "1" };
    const nodeClass = (questions: Record<string, unknown>[], fields = {}) =>
      ({
        template: {
          questions: { type: "decision_questions", value: questions },
          question_input_1: connection,
          ...fields,
        },
      }) as never;
    const renderConnectable = (
      questions: Record<string, unknown>[],
      fields = {},
    ) => {
      const handleNodeClass = jest.fn();
      const handleOnNewValue = jest.fn();
      render(
        <DecisionQuestionsComponent
          id="questions"
          value={questions}
          editNode={false}
          disabled={false}
          newQuestion={newQuestion}
          connectionPrefix="question_input_"
          fieldName="questions"
          nodeId="DecisionModel-1"
          nodeClass={nodeClass(questions, fields)}
          handleNodeClass={handleNodeClass}
          handleOnNewValue={handleOnNewValue}
        />,
      );
      return { handleNodeClass, handleOnNewValue };
    };
    const edgeInto = (field: string) => ({
      id: `edge-${field}`,
      source: "ChatInput-1",
      target: "DecisionModel-1",
      targetHandle: JSON.stringify({ fieldName: field }).replace(/"/g, "œ"),
    });

    afterEach(() => useFlowStore.setState({ edges: [] }));

    it("draws a handle on each question card", () => {
      renderConnectable([first]);
      expect(screen.getByTestId("handle_question_input_1")).toBeInTheDocument();
    });

    it("adds a connection field with each question it adds", () => {
      const { handleNodeClass } = renderConnectable([first]);
      fireEvent.click(screen.getByTestId("questions_add"));
      const [[updated]] = handleNodeClass.mock.calls;
      const [, added] = updated.template.questions.value;
      expect(added.id).toMatch(/^[a-z0-9]+$/);
      expect(updated.template[`question_input_${added.id}`]).toMatchObject({
        name: `question_input_${added.id}`,
        input_types: ["Message"],
        show: false,
      });
    });

    it("removes an added question's field and the edge into it", () => {
      const deleteEdge = jest.fn();
      useFlowStore.setState({
        edges: [edgeInto("question_input_x1")] as never,
        deleteEdge,
      });
      const second = { ...newQuestion, id: "x1" };
      const { handleNodeClass } = renderConnectable([first, second], {
        question_input_x1: { ...connection, name: "question_input_x1" },
      });
      fireEvent.click(screen.getByTestId("questions_remove_1"));
      expect(deleteEdge).toHaveBeenCalledWith(["edge-question_input_x1"]);
      const [[updated]] = handleNodeClass.mock.calls;
      expect(updated.template.questions.value).toEqual([first]);
      expect(updated.template.question_input_x1).toBeUndefined();
    });

    it("shows a connected question instead of its text box", () => {
      useFlowStore.setState({ edges: [edgeInto("question_input_1")] as never });
      renderConnectable([first]);
      expect(
        screen.getByTestId("questions_question_connected_0"),
      ).toHaveTextContent("Connected");
      expect(screen.queryByLabelText("Question 1 text")).toBeNull();
    });
  });
});
