import type { AllNodeType, EdgeType, NodeDataType } from "../../types/flow";
import {
  filterHiddenFieldsEdges,
  questionConnectionFields,
} from "../reactflowUtils";

// A Decision Model's question cards draw the handles of hidden connection fields.
const decisionNode = (questionsShown: boolean) =>
  ({
    id: "DecisionModel-1",
    type: "genericNode",
    data: {
      id: "DecisionModel-1",
      type: "DecisionModel",
      node: {
        display_name: "Decision Model",
        template: {
          questions: {
            type: "decision_questions",
            show: questionsShown,
            connection_prefix: "question_input_",
            value: [
              {
                id: "1",
                kind: "Noul",
                input_field: "question",
                yes_input_field: "yes_description",
              },
              { id: "x1" },
              { id: "x2" },
            ],
          },
          question: { show: false, display_name: "Question 1" },
          yes_description: { show: false, display_name: "What Yes Means" },
          question_input_x1: { show: false, display_name: "Question 2" },
          structured_context: { show: false, display_name: "Structured" },
        },
      },
    },
  }) as unknown as AllNodeType;

const edgeInto = (fieldName: string) =>
  ({
    id: `edge-${fieldName}`,
    source: "ChatInput-1",
    target: "DecisionModel-1",
    data: { targetHandle: { fieldName } },
  }) as unknown as EdgeType;

describe("edges into a question card's connection", () => {
  it("are kept while the question cards are shown", () => {
    const edge = edgeInto("question_input_x1");
    expect(filterHiddenFieldsEdges(edge, [edge], decisionNode(true))).toEqual([
      edge,
    ]);
  });

  it("are removed when the cards are hidden, as for any hidden field", () => {
    const edge = edgeInto("question_input_x1");
    expect(filterHiddenFieldsEdges(edge, [edge], decisionNode(false))).toEqual(
      [],
    );
  });

  it("don't spare other hidden fields of the same node", () => {
    const edge = edgeInto("structured_context");
    expect(filterHiddenFieldsEdges(edge, [edge], decisionNode(true))).toEqual(
      [],
    );
  });

  it("include the old Question and What Yes Means fields a migrated question names", () => {
    for (const field of ["question", "yes_description"]) {
      const edge = edgeInto(field);
      expect(filterHiddenFieldsEdges(edge, [edge], decisionNode(true))).toEqual(
        [edge],
      );
    }
  });
});

// A minimized node draws these handles itself, since it hides the cards.
describe("the connection fields a question list draws", () => {
  const template = (questionsShown: boolean) =>
    (decisionNode(questionsShown).data as NodeDataType).node!.template;

  it("name each question's field and number, skipping fields not on the node", () => {
    expect(questionConnectionFields(template(true))).toEqual([
      { text: "question", fieldName: "question", number: 1 },
      { text: "yes_description", fieldName: "yes_description", number: 1 },
      { text: "question", fieldName: "question_input_x1", number: 2 },
    ]);
  });

  it("are none while the question cards are hidden", () => {
    expect(questionConnectionFields(template(false))).toEqual([]);
  });

  it("are none while the question list is off the canvas", () => {
    const offCanvas = template(true);
    offCanvas.questions = { ...offCanvas.questions, advanced: true };
    expect(questionConnectionFields(offCanvas)).toEqual([]);
  });
});
