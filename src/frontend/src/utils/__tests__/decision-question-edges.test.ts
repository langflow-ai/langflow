import type { AllNodeType, EdgeType } from "../../types/flow";
import { filterHiddenFieldsEdges } from "../reactflowUtils";

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
            value: [{ id: "1", input_field: "question" }],
          },
          question: { show: false, display_name: "Question 1" },
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

  it("include the old Question field a migrated question names", () => {
    const edge = edgeInto("question");
    expect(filterHiddenFieldsEdges(edge, [edge], decisionNode(true))).toEqual([
      edge,
    ]);
  });
});
