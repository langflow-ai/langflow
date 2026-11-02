import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import DecisionQuestionsComponent from "../decision-questions";

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
  options: [
    { id: "a", label: "Option A", description: "" },
    { id: "b", label: "Option B", description: "" },
  ],
  levels: [{ id: "low", label: "Low", description: "" }],
};
const team = {
  ...newQuestion,
  id: "1",
  name: "team",
  question: "Which team should handle this?",
};
const urgent = { ...newQuestion, id: "x1", name: "", kind: "Noul" };

const connection = {
  type: "str",
  input_types: ["Message"],
  show: false,
  value: "",
  name: "question_input_1",
  display_name: "Question 1",
};

const renderQuestions = (
  questions: Record<string, unknown>[],
  fields: Record<string, unknown> = {
    question_input_x1: { ...connection, name: "question_input_x1" },
  },
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
      nodeClass={
        {
          template: {
            questions: { type: "decision_questions", value: questions },
            question_input_1: connection,
            ...fields,
          },
        } as never
      }
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

describe("DecisionQuestionsComponent on the node", () => {
  it("shows one compact row per question with its handle", () => {
    renderQuestions([team, urgent]);
    const first = screen.getByTestId("questions_question_0");
    expect(first).toHaveTextContent("team");
    expect(first).toHaveTextContent("Choice");
    expect(first).toHaveTextContent("Options: 2");
    expect(first).toHaveTextContent("Which team should handle this?");
    const second = screen.getByTestId("questions_question_1");
    expect(second).toHaveTextContent("q2");
    expect(second).toHaveTextContent("Yes / No");
    expect(screen.getByTestId("handle_question_input_1")).toBeInTheDocument();
    expect(screen.getByTestId("handle_question_input_x1")).toBeInTheDocument();
  });

  it("marks a connected question", () => {
    useFlowStore.setState({ edges: [edgeInto("question_input_x1")] as never });
    renderQuestions([team, urgent]);
    expect(screen.getByTestId("questions_question_1")).toHaveTextContent(
      "Connected",
    );
  });

  it("starts empty, offering to add questions", () => {
    renderQuestions([]);
    expect(screen.queryByTestId("questions_question_0")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Add questions/ }));
    expect(screen.getByTestId("questions_modal_name")).toHaveValue("");
  });

  it("opens the editor on the question that was clicked", () => {
    renderQuestions([team, urgent]);
    fireEvent.click(screen.getByTestId("questions_question_1"));
    expect(screen.getByTestId("questions_modal_name")).toHaveValue("");
    expect(screen.getByTestId("questions_modal_yes_description")).toBeVisible();
  });
});

describe("the question editor", () => {
  it("keeps edits until Done and then saves them", () => {
    const { handleNodeClass } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.change(screen.getByTestId("questions_modal_question_text"), {
      target: { value: "Who handles it?" },
    });
    expect(handleNodeClass).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.questions.value).toEqual([
      { ...team, question: "Who handles it?" },
    ]);
  });

  it("discards edits when cancelled", () => {
    const { handleNodeClass, handleOnNewValue } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.change(screen.getByTestId("questions_modal_name"), {
      target: { value: "changed" },
    });
    fireEvent.click(screen.getByTestId("btn-cancel-modal"));
    expect(handleNodeClass).not.toHaveBeenCalled();
    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("adds a question with its own connection field", () => {
    const { handleNodeClass } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.click(screen.getByTestId("questions_modal_add"));
    fireEvent.change(screen.getByTestId("questions_modal_question_text"), {
      target: { value: "Is it urgent?" },
    });
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    const [[updated]] = handleNodeClass.mock.calls;
    const [, added] = updated.template.questions.value;
    expect(added).toMatchObject({ kind: "Choice", question: "Is it urgent?" });
    expect(updated.template[`question_input_${added.id}`]).toMatchObject({
      name: `question_input_${added.id}`,
      input_types: ["Message"],
      show: false,
    });
  });

  it("deletes a question with its connection field and the edge into it", () => {
    const deleteEdge = jest.fn();
    useFlowStore.setState({
      edges: [edgeInto("question_input_x1")] as never,
      deleteEdge,
    });
    const { handleNodeClass } = renderQuestions([team, urgent]);
    fireEvent.click(screen.getByTestId("questions_question_1"));
    fireEvent.click(screen.getByTestId("questions_modal_delete"));
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    expect(deleteEdge).toHaveBeenCalledWith(["edge-question_input_x1"]);
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.questions.value).toEqual([team]);
    expect(updated.template.question_input_x1).toBeUndefined();
  });

  it("can delete every question", () => {
    const { handleNodeClass } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.click(screen.getByTestId("questions_modal_delete"));
    expect(screen.getByText(/No questions yet/)).toBeInTheDocument();
    expect(screen.getByTestId("questions_modal_delete")).toBeDisabled();
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.questions.value).toEqual([]);
  });

  it("saves a question without text, which a connection can supply later", () => {
    const { handleNodeClass } = renderQuestions([team, urgent]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.questions.value).toEqual([team, urgent]);
  });

  it("edits the selected type's options or levels", async () => {
    const { handleNodeClass } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    // Radix tabs select on pointer down, which fireEvent.click doesn't send.
    await userEvent.setup().click(screen.getByRole("tab", { name: "Score" }));
    fireEvent.click(screen.getByTestId("questions_modal_add_row"));
    const row = within(screen.getByTestId("questions_modal_row_1"));
    fireEvent.change(row.getByLabelText("ID 2"), { target: { value: "high" } });
    fireEvent.change(row.getByLabelText("Label 2"), {
      target: { value: "High" },
    });
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.questions.value[0]).toMatchObject({
      kind: "Score",
      levels: [
        { id: "low", label: "Low", description: "" },
        { id: "high", label: "High", description: "" },
      ],
      options: team.options,
    });
  });

  it("shows a connected question as supplied by another component", () => {
    useFlowStore.setState({ edges: [edgeInto("question_input_1")] as never });
    renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    expect(
      screen.getByTestId("questions_modal_question_connected"),
    ).toHaveTextContent("Another component supplies this question's text.");
    expect(screen.queryByTestId("questions_modal_question_text")).toBeNull();
  });

  it("removes the edge into question 1 but keeps the field new questions copy", () => {
    const deleteEdge = jest.fn();
    useFlowStore.setState({
      edges: [edgeInto("question_input_1")] as never,
      deleteEdge,
    });
    const { handleNodeClass } = renderQuestions([team]);
    fireEvent.click(screen.getByTestId("questions_edit"));
    fireEvent.click(screen.getByTestId("questions_modal_delete"));
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    expect(deleteEdge).toHaveBeenCalledWith(["edge-question_input_1"]);
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.question_input_1).toEqual(connection);
  });

  it("takes the undo snapshot before removing a connected question's edge", () => {
    const calls: string[] = [];
    useFlowStore.setState({
      edges: [edgeInto("question_input_x1")] as never,
      deleteEdge: () => calls.push("deleteEdge"),
    });
    const takeSnapshot = useFlowsManagerStore.getState().takeSnapshot;
    useFlowsManagerStore.setState({
      takeSnapshot: () => calls.push("snapshot"),
    });
    renderQuestions([team, urgent]);
    fireEvent.click(screen.getByTestId("questions_question_1"));
    fireEvent.click(screen.getByTestId("questions_modal_delete"));
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    useFlowsManagerStore.setState({ takeSnapshot });
    expect(calls).toEqual(["snapshot", "deleteEdge"]);
  });

  it("draws no handles on its cards while the node is minimized", () => {
    useFlowStore.setState({
      nodes: [{ id: "DecisionModel-1", data: { showNode: false } }] as never,
    });
    renderQuestions([team, urgent]);
    expect(screen.queryByTestId("handle_question_input_1")).toBeNull();
    expect(screen.queryByTestId("handle_question_input_x1")).toBeNull();
    useFlowStore.setState({ nodes: [] });
  });

  it("keeps a migrated question wired through the old Question field", () => {
    useFlowStore.setState({ edges: [edgeInto("question")] as never });
    const migrated = { ...team, input_field: "question" };
    renderQuestions([migrated], {
      question: { ...connection, name: "question" },
    });
    expect(screen.getByTestId("handle_question")).toBeInTheDocument();
    expect(screen.getByTestId("questions_question_0")).toHaveTextContent(
      "Connected",
    );
  });
});

describe("a Noul migrated from the old Yes / No fields", () => {
  const migrated = {
    ...urgent,
    id: "1",
    input_field: "question",
    yes_input_field: "yes_description",
    no_input_field: "no_description",
  };
  const fields = {
    question: { ...connection, name: "question" },
    yes_description: { ...connection, name: "yes_description" },
    no_description: { ...connection, name: "no_description" },
  };

  it("keeps What Yes and What No Means connectable", () => {
    useFlowStore.setState({ edges: [edgeInto("yes_description")] as never });
    renderQuestions([migrated], fields);
    expect(screen.getByTestId("handle_yes_description")).toBeInTheDocument();
    expect(screen.getByTestId("handle_no_description")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("questions_edit"));
    expect(
      screen.getByTestId("questions_modal_yes_description_connected"),
    ).toHaveTextContent("Connected");
    expect(screen.getByTestId("questions_modal_no_description")).toBeVisible();
  });

  it("drops their connections once it is no longer a Noul", async () => {
    const deleteEdge = jest.fn();
    useFlowStore.setState({
      edges: [edgeInto("yes_description")] as never,
      deleteEdge,
    });
    const { handleNodeClass } = renderQuestions([migrated], fields);
    fireEvent.click(screen.getByTestId("questions_edit"));
    await userEvent.setup().click(screen.getByRole("tab", { name: "Choice" }));
    fireEvent.click(screen.getByTestId("questions_modal_done"));
    expect(deleteEdge).toHaveBeenCalledWith(["edge-yes_description"]);
    const [[updated]] = handleNodeClass.mock.calls;
    expect(updated.template.yes_description).toBeUndefined();
    expect(updated.template.no_description).toBeUndefined();
    expect(updated.template.question).toEqual(fields.question);
  });
});
