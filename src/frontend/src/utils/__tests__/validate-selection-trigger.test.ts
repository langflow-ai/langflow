import type { Edge, Node, OnSelectionChangeParams } from "@xyflow/react";
import { validateSelection } from "../reactflowUtils";

const GROUP_TRIGGER_MESSAGE = "Select non-trigger components only";

function node(id: string, type: string, metadata?: object): Node {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type, node: { template: {}, outputs: [], metadata } },
  };
}

const schedule = node("schedule", "ScheduleTrigger", {
  trigger_kind: "schedule",
});
const parser = node("parser", "ParserComponent");
const prompt = node("prompt", "Prompt");
const scheduleToParser: Edge = {
  id: "e1",
  source: schedule.id,
  target: parser.id,
};
const promptToParser: Edge = { id: "e2", source: prompt.id, target: parser.id };

const selectionOf = (nodes: Node[]): OnSelectionChangeParams => ({
  nodes,
  edges: [],
});

describe("validateSelection", () => {
  it("should_refuse_grouping_when_the_selection_contains_a_trigger", () => {
    const errors = validateSelection(selectionOf([schedule, parser]), [
      scheduleToParser,
    ]);

    expect(errors).toEqual([GROUP_TRIGGER_MESSAGE]);
  });

  it("should_allow_grouping_when_no_selected_node_is_a_trigger", () => {
    const errors = validateSelection(selectionOf([prompt, parser]), [
      promptToParser,
    ]);

    expect(errors).toEqual([]);
  });
});
