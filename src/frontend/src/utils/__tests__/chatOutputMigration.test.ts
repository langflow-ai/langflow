import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cloneDeep } from "lodash";
import type { APIClassType } from "@/types/api";
import type { AllNodeType, EdgeType, GenericNodeType } from "@/types/flow";
import { cleanEdges, scapeJSONParse } from "../reactflowUtils";
import fixture from "./upgradeComponentEdgeLoss.fixture.json";

const index = JSON.parse(
  readFileSync(
    resolve(__dirname, "../../../../lfx/src/lfx/_assets/component_index.json"),
    "utf8",
  ),
);
const currentChatOutput: APIClassType = index.entries.find(
  ([, components]: [string, Record<string, APIClassType>]) =>
    components.ChatOutput,
)[1].ChatOutput;

// This fixture has the MessageInput/str declaration and serialized handle also saved by the
// Youtube Analysis flows shipped in 1.12.6 and 1.13.0. Exercise production cleanEdges.
function updatedFlow() {
  const nodes = cloneDeep(fixture.nodes) as unknown as AllNodeType[];
  const edges = cloneDeep(fixture.edges) as unknown as EdgeType[];
  const chatOutput = nodes.find(
    (node) => node.data.type === "ChatOutput",
  ) as GenericNodeType;
  chatOutput.data.node = cloneDeep(currentChatOutput);
  const inputEdge = edges.find((edge) => edge.target === chatOutput.id)!;
  return { nodes, edges, chatOutput, inputEdge };
}

describe("Chat Output historical input migration", () => {
  it("keeps the connection and rewrites both saved handles to the current field type", () => {
    const { nodes, edges, inputEdge } = updatedFlow();
    expect(scapeJSONParse(inputEdge.targetHandle!).type).toBe("str");

    const result = cleanEdges(nodes, edges);
    const migrated = result.edges.find(
      (edge) => edge.target === inputEdge.target,
    );

    expect(result.brokenEdges).toHaveLength(0);
    expect(result.edges).toHaveLength(edges.length);
    expect(migrated).toBeDefined();
    expect(scapeJSONParse(migrated!.targetHandle!).type).toBe("other");
    expect(migrated!.data!.targetHandle.type).toBe("other");
    expect(migrated!.id).toContain(migrated!.targetHandle!);
    expect(scapeJSONParse(inputEdge.targetHandle!).type).toBe("str");
  });

  it("leaves a current other-typed connection usable on the next cleanup", () => {
    const { nodes, edges } = updatedFlow();
    const migrated = cleanEdges(nodes, edges);
    expect(cleanEdges(nodes, migrated.edges)).toEqual(migrated);
  });

  it.each([
    "different component",
    "incompatible input",
    "different field type",
  ])("still reports a broken connection for %s", (change) => {
    const { nodes, edges, chatOutput, inputEdge } = updatedFlow();
    if (change === "different component") {
      Object.assign(chatOutput.data.node!, {
        metadata: { component_class_name: "OtherOutput" },
      });
    } else if (change === "incompatible input") {
      chatOutput.data.node!.template.input_value.input_types = [
        "LanguageModel",
      ];
    } else {
      chatOutput.data.node!.template.input_value.type = "int";
    }
    const result = cleanEdges(nodes, edges);
    expect(result.edges.some((edge) => edge.target === inputEdge.target)).toBe(
      false,
    );
    expect(result.brokenEdges).toHaveLength(1);
  });
});
